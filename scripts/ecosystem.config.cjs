/**
 * PM2 ecosystem for Myanmar news → Telegram watcher.
 *
 * From the docker project root (folder that contains .env and docker-compose.yml):
 *   pm2 start scripts/ecosystem.config.cjs
 *   pm2 save && pm2 startup
 *
 * Logs: pm2 logs myanmar-news-telegram
 * Test: python3 -u scripts/myanmar_news_telegram_watcher.py --test
 */

const path = require("path");

const root = path.resolve(__dirname, "..");

module.exports = {
  apps: [
    {
      name: "myanmar-news-telegram",
      cwd: root,
      script: "scripts/myanmar_news_telegram_watcher.py",
      interpreter: "python3",
      interpreter_args: "-u",
      args: "--interval 300 --max-per-run 10",
      autorestart: true,
      max_restarts: 50,
      min_uptime: "10s",
      restart_delay: 5000,
      watch: false,
      // .env is loaded by the Python script from project root
      env: {
        PYTHONUNBUFFERED: "1",
      },
    },
  ],
};
