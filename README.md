# 🚀 Mega VM Monitoring Dashboard

[![Version](https://img.shields.io/badge/version-4.0-purple)](https://github.com/RCandidate/vm_monitoring)
[![Status](https://img.shields.io/badge/status-production-brightgreen)](https://github.com/RCandidate/vm_monitoring)
[![License](https://img.shields.io/badge/license-MIT-purple)](LICENSE)

> **Enterprise-grade virtual machine monitoring solution with real-time telemetry, intelligent anomaly detection, and scroll-stopping visualizations** 🌈

## ✨ Features That Will Blow Your Mind

| Feature | Description |
|---------|-------------|
| 📊 **Real-time Charts** | CPU load, disk space, and uptime monitoring with smooth animations |
| 🎨 **Smart Color Coding** | VM groups get distinct colors with interpolated gradients for multi-VM groups |
| ⚠️ **Anomaly Detection** | Automatic alerts for VMs with suspiciously low CPU load (potential software crashes) |
| 🔄 **Time Range Selector** | 1h, 6h, or 12h history views |
| ✨ **Golden Shimmer Effect** | VMs with 64+ hours uptime get a beautiful animated highlight |
| 🧵 **Thread Telemetry** | Hover tooltips show thread counts, BAS versions, and project versions |
| 📐 **Smart Scaling** | Disk charts automatically adjust Y-axis based on actual free space |

## 🖼️ Dashboard Preview

<img width="1412" height="471" alt="image" src="https://github.com/user-attachments/assets/a4eb17e4-f4b4-4314-9204-bcb743b5c9d5" />


*The dashboard features real-time CPU load graphs, free disk space monitoring, and an eye-catching uptime bar chart with logarithmic scale.*

## 🛠️ Tech Stack

```yaml
Frontend:
  - HTML5 + CSS3 (Flexbox layout)
  - Chart.js + chartjs-adapter-date-fns
  - Vanilla JavaScript (no frameworks!)
  
Backend Integration:
  - Jinja2 templating
  - RESTful data endpoints
  - Timezone: Europe/Moscow 🇷🇺
```

##🚀 Quick Start
Prerequisites
Python 3.8+
A sense of wonder ✨

##**Installation**

# Clone the repository
git clone https://github.com/RCandidate/vm_monitoring.git
cd vm_monitoring

# Install dependencies
pip install -r requirements.txt

# Configure your VM monitoring agents
cp .env.example .env
# Edit .env with your configuration

# Launch the dashboard
python app.py
Visit http://localhost:5000/dashboard and prepare to be amazed.

##🎯 How It Works
Color Magic
- Cyber group: Purple gradient from #9400D3 to #4B0082
- Other groups: Distinct colors based on group name hash
- Multi-VM groups: Smooth color interpolation across VMs

##Uptime Rainbow 🌈

Hours 0-64+ → #000000 → #FF0000 → #FFA500 → #00FF00 → #00FFFF → #0000FF → #800080 → #FFFFFF
Yes, that's a full rainbow transition. Because uptime deserves celebration.

##Smart Scaling
- Disk space >60GB displays as 60GB (cleaner visualization)
- Y-axis minimum automatically adjusts to your actual free space
- Logarithmic scale for uptime (0.01 to 64+ hours)


##⚠️ Warning System
The dashboard automatically highlights VMs with suspiciously low CPU load (<0.5% average) — perfect for catching crashed or hung processes before users notice.

##📈 Version History
v4.3. (Current)  # Security update (.env), agent + nginx configs, project cleanup
v3.0.            # Initial dashboard with basic charts

##🤝 Contributing
Found a bug? Have an idea for an even cooler gradient? Open an issue or submit a PR!

Fork the repository

Create your feature branch (git checkout -b feature/amazing-gradient)

Commit your changes (git commit -m 'Add more purple')

Push to the branch (git push origin feature/amazing-gradient)

Open a Pull Request

##🐛 Known Issues
- Golden shimmer effect may cause spontaneous dancing in your peripheral vision
- May induce desire to reach 64+ hours uptime just to see the animation

##📝 License
MIT — go wild, just keep the purple theme intact.

##🙏 Acknowledgments
- Chart.js team for making graphs beautiful
- The color purple for being majestic
- Coffee ☕

###Built with 💜 and an unreasonable amount of CSS gradients
