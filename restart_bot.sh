#!/bin/bash
# restart_bot.sh
# Restart the Fundraiser Flask Bot service safely

SERVICE="2025-andree-fundraiser-bot.service"

echo "Stopping $SERVICE..."
sudo systemctl stop $SERVICE

echo "Reloading systemd units..."
sudo systemctl daemon-reload

echo "Starting $SERVICE..."
sudo systemctl start $SERVICE

echo "Checking status..."
sudo systemctl status $SERVICE --no-pager -l
