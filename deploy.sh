#!/bin/bash

echo "Knocking on ports..."
for x in $SSH_PORTS; do sudo nmap -Pn --max-retries 0 -p $x $SSH_HOST; done

echo "Port checking..."
nmap -p $SSH_PORT $SSH_HOST

echo "Connecting to SSH..."
if ! ssh -tt -o StrictHostKeyChecking=no $SSH_USERNAME@$SSH_HOST -p $SSH_PORT << EOF
  cd /home/nik/portfolios
  git pull
  python -m pip install --upgrade pip
  pip install -r requirements.txt
  sudo systemctl restart portfolios
  sudo systemctl restart celery
  sudo systemctl restart nginx
EOF
then
  echo "SSH connection failed!"
  exit 1
fi

echo "Deployment completed!"
