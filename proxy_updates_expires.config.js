module.exports = {
  apps: [
    {
      name: "proxy-updates-expires",
      script: "/home/antigravity/projects/python/run_proxy_updates_expires.py",
      interpreter: "/home/dixit/venv/bin/python",
      cwd: "/home/antigravity/projects/python",
      autorestart: false,
      cron_restart: "0 9 * * *",             // 09:00 AM IST daily (server is in Asia/Kolkata timezone)
      out_file: "/home/antigravity/logs/proxy_updates_expires.out.log",
      error_file: "/home/antigravity/logs/proxy_updates_expires.err.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss"
    }
  ]
};
