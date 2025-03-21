#!/bin/bash

echo "Knocking on ports..."
for x in $SSH_PORTS; do
  sudo nmap -Pn --max-retries 0 -p $x $SSH_HOST;
done

echo "Port checking..."
if ! nmap -p $SSH_PORT $SSH_HOST | grep -q "open"; then
  echo "Port SSH is not open!"
  exit 1
fi

echo "Connecting to SSH..."
eval "$(ssh-agent -s)"
echo "$SSH_KEY_PASSPHRASE" | ssh-add ~/.ssh/id_ed25519

if ! ssh -o StrictHostKeyChecking=no $SSH_USERNAME@$SSH_HOST -p $SSH_PORT << EOF
  cd /home/nik/portfolios
  git pull
  python3 -m pip install --upgrade pip
  pip install -r requirements.txt

  if ! echo "$SUDO_PASSWORD" | sudo -S systemctl restart portfolios; then
    echo "Failed to restart portfolios!"
    exit 1
  fi

  if ! echo "$SUDO_PASSWORD" | sudo -S systemctl restart celery; then
    echo "Failed to restart celery!"
    exit 1
  fi

  if ! echo "$SUDO_PASSWORD" | sudo -S systemctl restart nginx; then
    echo "Failed to restart nginx!"
    exit 1
  fi
EOF
then
  echo "SSH connection failed!"
  exit 1
fi

echo "Deployment completed!"
