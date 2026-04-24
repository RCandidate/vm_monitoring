# server.py
# v4
from flask import Flask, request, jsonify, render_template
import mysql.connector
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo




import os
from dotenv import load_dotenv
load_dotenv() # Загружает переменные из файла .env
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_USER = os.getenv('DB_USER')
DB_HOST = os.getenv('DB_HOST')
#DB_NAME = os.getenv('DB_NAME')
DB_NAME = os.getenv('DB_NAME', 'bas_monitor_2')

app = Flask(__name__)
MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def get_db_connection(database):
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )


@app.route('/metrics', methods=['POST'])
def receive_metrics():
    db = None
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        moscow_time = datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S')
        vm_id = str(data.get('vm_id', 'UNKNOWN'))[:100]

        vm_profile = data.get('vm_profile')
        if not vm_profile or str(vm_profile).strip().lower() in ('null', 'none', ''):
            vm_profile = 'Cyber'
        else:
            vm_profile = str(vm_profile)[:50]

        vm_bas_version = data.get('vm_bas_version', 'N/A')
        if not vm_bas_version or str(vm_bas_version).strip().lower() in ('null', 'none', ''):
            vm_bas_version = 'N/A'
        else:
            vm_bas_version = str(vm_bas_version)[:50]

        vm_project_version = data.get('vm_project_version', 'N/A')
        if not vm_project_version or str(vm_project_version).strip().lower() in ('null', 'none', ''):
            vm_project_version = 'N/A'
        else:
            vm_project_version = str(vm_project_version)[:50]

        vm_threads_raw = data.get('vm_threads', '0')
        try:
            threads = int(vm_threads_raw)
        except (ValueError, TypeError):
            threads = 0

        cpu = float(data.get('cpu', 0.0)) if data.get('cpu') is not None else 0.0
        disk_free = int(data.get('disk_free', 0)) if data.get('disk_free') is not None else 0

        # Uptime (в секундах)
        uptime_raw = data.get('uptime_seconds')
        try:
            uptime_seconds = int(uptime_raw) if uptime_raw is not None else 0
        except (ValueError, TypeError):
            uptime_seconds = 0

        bas_title_raw = data.get('bas_title')
        if bas_title_raw is None:
            bas_title = ""
        elif isinstance(bas_title_raw, (dict, list)):
            bas_title = str(bas_title_raw)[:255]
        else:
            bas_title = str(bas_title_raw)[:255]

        success_events = data.get('success_events', [])
        if not isinstance(success_events, list):
            success_events = []
        success_count = len(success_events)

        db = get_db_connection("bas_monitor_2")
        cursor = db.cursor()
        
        cursor.execute("""
            INSERT INTO metrics (
                vm_id, vm_group, timestamp, cpu, disk_free, uptime_seconds,
                threads, bas_title, success, vm_bas_version, vm_project_version
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            vm_id, vm_profile, moscow_time, cpu, disk_free, uptime_seconds,
            threads, bas_title, success_count, vm_bas_version, vm_project_version
        ))

        db.commit()
        cursor.close()

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500

    finally:
        if db is not None:
            try:
                db.close()
            except:
                pass


@app.route('/dashboard')
def dashboard():
    try:
        time_range = request.args.get('time_range', '1h')
        if time_range == '12h':
            hours = 12
        elif time_range == '6h':
            hours = 6
        else:
            hours = 1

        now_moscow = datetime.now(MOSCOW_TZ)
        time_threshold = now_moscow - timedelta(hours=hours)
        time_threshold_str = time_threshold.strftime('%Y-%m-%d %H:%M:%S')

        conn = get_db_connection("bas_monitor_2")
        cursor = conn.cursor(dictionary=True)

        # Данные для линейных графиков (CPU / Disk)
        cursor.execute("""
            SELECT vm_id, vm_group, cpu, disk_free, threads, timestamp
            FROM metrics
            WHERE timestamp >= %s
            ORDER BY timestamp ASC
        """, (time_threshold_str,))
        raw_data = cursor.fetchall()

        vms_by_group = {}
        for row in raw_data:
            vm = row['vm_id']
            group_raw = row['vm_group']
            group = 'Cyber' if not group_raw or str(group_raw).strip().lower() in ('null', 'none', '') else str(group_raw)

            if group not in vms_by_group:
                vms_by_group[group] = {}
            if vm not in vms_by_group[group]:
                vms_by_group[group][vm] = {'cpu': [], 'disk': [], 'threads': []}

            time_local = row['timestamp'].strftime('%Y-%m-%dT%H:%M:%S') + '+03:00'
            vms_by_group[group][vm]['cpu'].append({'x': time_local, 'y': float(row['cpu'])})
            vms_by_group[group][vm]['disk'].append({'x': time_local, 'y': row['disk_free']})
            vms_by_group[group][vm]['threads'].append({'x': time_local, 'y': row['threads']})

        group_order = []
        if 'Cyber' in vms_by_group:
            group_order.append('Cyber')
        for group in vms_by_group:
            if group != 'Cyber':
                group_order.append(group)

        # VM с потенциальным сбоем (низкий CPU)
        cursor.execute("""
            SELECT vm_id, vm_group, AVG(cpu) as avg_cpu, vm_bas_version, vm_project_version
            FROM metrics
            WHERE timestamp >= %s
            AND vm_id NOT IN (
                SELECT DISTINCT vm_id FROM metrics WHERE timestamp >= %s AND cpu > 20
            )
            GROUP BY vm_id, vm_group, vm_bas_version, vm_project_version
            ORDER BY AVG(cpu) ASC
        """, (time_threshold_str, time_threshold_str))
        low_cpu_vms = cursor.fetchall()
        failing_vm_ids = {row['vm_id'] for row in low_cpu_vms}




        # ВАЖНО: Добавили фильтр WHERE timestamp >= %s ВНУТРЬ подзапроса.
        # Теперь мы сначала отбираем только те ВМ, которые "ожили" за последние hours,
        # а затем уже среди них ищем самый свежий отчет.
        cursor.execute("""
            SELECT vm_id, vm_group, threads, vm_project_version, vm_bas_version
            FROM (
                SELECT vm_id, vm_group, threads, vm_project_version, vm_bas_version,
                       ROW_NUMBER() OVER (PARTITION BY vm_id ORDER BY timestamp DESC) as rn
                FROM metrics
                WHERE timestamp >= %s
            ) ranked
            WHERE rn = 1
        """, (time_threshold_str,))
        latest_vms = cursor.fetchall()



        # Запрос последних значений uptime для графика
        cursor.execute("""
            SELECT vm_id, uptime_seconds FROM (
                SELECT vm_id, uptime_seconds,
                       ROW_NUMBER() OVER (PARTITION BY vm_id ORDER BY timestamp DESC) as rn
                FROM metrics
            ) ranked
            WHERE rn = 1
        """)
        uptime_raw = cursor.fetchall()
        uptime_data = {row['vm_id']: row['uptime_seconds'] for row in uptime_raw}

        # Версии ПО для подсказок 
        cursor.execute("""
            SELECT vm_id, vm_bas_version, vm_project_version FROM (
                SELECT vm_id, vm_bas_version, vm_project_version,
                       ROW_NUMBER() OVER (PARTITION BY vm_id ORDER BY timestamp DESC) as rn
                FROM metrics
            ) ranked
            WHERE rn = 1
        """)
        latest_versions_raw = cursor.fetchall()
        vm_versions = {
            row['vm_id']: {
                'bas_version': row['vm_bas_version'],
                'project_version': row['vm_project_version']
            } for row in latest_versions_raw
        }

        conn.close()
        # === Логика breakdown: РАЗДЕЛЬНЫЕ столбцы для Project и BAS ===
        profile_stats = {}
        # Структура: ключом теперь выступает кортеж (Project, BAS_Version)

        for row in latest_vms:
            threads = row['threads'] if row['threads'] is not None else 0
            group_raw = row['vm_group']
            project = row['vm_project_version'] if row['vm_project_version'] else 'N/A'
            bas_ver = row['vm_bas_version'] if row['vm_bas_version'] else 'N/A'
            vm_id = row['vm_id']

            group = 'Cyber' if not group_raw or str(group_raw).strip().lower() in ('null', 'none', '') else str(group_raw)
            individual_profiles = group.split('+')

            for profile in individual_profiles:
                profile = profile.strip()
                if not profile:
                    continue
                if profile not in profile_stats:
                    profile_stats[profile] = {}
                
                # 🆕 Используем кортеж (проект, версия BAS) как уникальный ключ
                item_key = (project, bas_ver)

                if item_key not in profile_stats[profile]:
                    profile_stats[profile][item_key] = {
                        'threads': 0,
                        'has_active': False,
                        'has_fail': False
                    }

                profile_stats[profile][item_key]['threads'] += threads
                if vm_id in failing_vm_ids:
                    profile_stats[profile][item_key]['has_fail'] = True
                else:
                    profile_stats[profile][item_key]['has_active'] = True

        # Формируем строки для шаблона с ДВУМЯ раздельными breakdown-списками
        group_rows = []
        for profile, items in profile_stats.items():
            total_threads = sum(p['threads'] for p in items.values())

            # Сортируем по количеству потоков (убывание)
            sorted_items = sorted(items.items(), key=lambda x: x[1]['threads'], reverse=True)

            breakdown_project = []
            breakdown_bas = []

            # 🆕 Распаковываем кортеж (project, bas_ver) из ключа
            for (proj_ver, bas_ver), data in sorted_items:
                css_class = "active-row" if data['has_active'] else "fail-row"

                # Project breakdown: "6 — Proj:7.3"
                breakdown_project.append({
                    'text': f"{data['threads']} — {proj_ver}",
                    'class': css_class
                })

                # BAS breakdown: "6 — BAS:29.3.1"
                breakdown_bas.append({
                    'text': f"{data['threads']} — {bas_ver}",
                    'class': css_class
                })

            group_rows.append({
                'group': profile,
                'threads': total_threads,
                'breakdown_project': breakdown_project,  
                'breakdown_bas': breakdown_bas            
            })

        group_rows.sort(key=lambda x: -x['threads'])


        return render_template(
            'dashboard.html',
            vms_by_group=vms_by_group,
            group_order=group_order,
            group_rows=group_rows,
            low_cpu_vms=low_cpu_vms,
            current_time_range=time_range,
            uptime_data=uptime_data,
            vm_versions=vm_versions,
            now_moscow=now_moscow.isoformat()
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"<h1>Dashboard Error</h1><pre>{e}</pre>", 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

