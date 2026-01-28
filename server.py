# server.py
# Version 3.3
from flask import Flask, request, jsonify, render_template
import mysql.connector
from datetime import datetime
from zoneinfo import ZoneInfo

app = Flask(__name__)
MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def get_db_connection(database):
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="***",
        database=database
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
            INSERT INTO metrics (vm_id, vm_group, timestamp, cpu, disk_free, threads, bas_title, success, vm_bas_version, vm_project_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (vm_id, vm_profile, moscow_time, cpu, disk_free, threads, bas_title, success_count, vm_bas_version, vm_project_version))

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

        conn = get_db_connection("bas_monitor_2")
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT vm_id, vm_group, cpu, disk_free, threads, timestamp
            FROM metrics
            WHERE timestamp >= NOW() - INTERVAL %s HOUR
            ORDER BY timestamp ASC
        """, (hours,))
        raw_data = cursor.fetchall()

        vms_by_group = {}

        for row in raw_data:
            vm = row['vm_id']
            group_raw = row['vm_group']
            if not group_raw or str(group_raw).strip().lower() in ('null', 'none', ''):
                group = 'Cyber'
            else:
                group = str(group_raw)

            if group not in vms_by_group:
                vms_by_group[group] = {}
            if vm not in vms_by_group[group]:
                vms_by_group[group][vm] = {'cpu': [], 'disk': []}

            time_local = row['timestamp'].strftime('%Y-%m-%dT%H:%M:%S') + '+03:00'

            vms_by_group[group][vm]['cpu'].append({'x': time_local, 'y': float(row['cpu'])})
            vms_by_group[group][vm]['disk'].append({'x': time_local, 'y': row['disk_free']})

        group_order = []
        if 'Cyber' in vms_by_group:
            group_order.append('Cyber')
        for group in vms_by_group:
            if group != 'Cyber':
                group_order.append(group)

        cursor.execute("""
            SELECT vm_id, vm_group, threads
            FROM (
                SELECT vm_id, vm_group, threads,
                       ROW_NUMBER() OVER (PARTITION BY vm_id ORDER BY timestamp DESC) as rn
                FROM metrics
                WHERE timestamp >= NOW() - INTERVAL 20 MINUTE
            ) ranked
            WHERE rn = 1
        """)
        latest_vms = cursor.fetchall()

        cursor.execute("""
            SELECT vm_id, vm_bas_version, vm_project_version
            FROM (
                SELECT vm_id, vm_bas_version, vm_project_version,
                       ROW_NUMBER() OVER (PARTITION BY vm_id ORDER BY timestamp DESC) as rn
                FROM metrics
            ) ranked
            WHERE rn = 1
        """)
        latest_versions_raw = cursor.fetchall()
        vm_versions = {row['vm_id']: {'bas_version': row['vm_bas_version'], 'project_version': row['vm_project_version']} for row in latest_versions_raw}

        cursor.execute("""
            SELECT vm_id, vm_group, AVG(cpu) as avg_cpu, vm_bas_version, vm_project_version
            FROM metrics
            WHERE timestamp >= NOW() - INTERVAL %s HOUR
            AND vm_id NOT IN (
                SELECT DISTINCT vm_id
                FROM metrics
                WHERE timestamp >= NOW() - INTERVAL %s HOUR
                AND cpu > 20
            )
            GROUP BY vm_id, vm_group, vm_bas_version, vm_project_version
            ORDER BY AVG(cpu) ASC
        """, (hours, hours))
        low_cpu_vms = cursor.fetchall()

        conn.close()

        # --- ИЗМЕНЕНИЕ: Новая логика подсчёта потоков по отдельным профилям ---
        profile_threads = {}
        for row in latest_vms:
            threads = row['threads'] if row['threads'] is not None else 0
            group_raw = row['vm_group']
            if not group_raw or str(group_raw).strip().lower() in ('null', 'none', ''):
                group = 'Cyber'
            else:
                group = str(group_raw)

            # Разделяем составной профиль на отдельные
            individual_profiles = group.split('+')
            for profile in individual_profiles:
                profile = profile.strip()
                if profile: # Убедимся, что строка не пустая
                    profile_threads[profile] = profile_threads.get(profile, 0) + threads

        # Преобразуем словарь в список для шаблона
        group_rows = [{'group': k, 'threads': v} for k, v in profile_threads.items()]
        group_rows.sort(key=lambda x: -x['threads'])

        return render_template(
            'dashboard.html',
            vms_by_group=vms_by_group,
            group_order=group_order,
            group_rows=group_rows,
            low_cpu_vms=low_cpu_vms,
            current_time_range=time_range,
            vm_versions=vm_versions
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"<h1>Dashboard Error</h1><pre>{e}</pre>", 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
