#!/bin/bash

echo "Knocking on ports..."
for x in $SSH_PORTS; do nmap -Pn --max-retries 0 -p $x $SSH_HOST; done

echo "Connecting to SSH..."
ssh -o StrictHostKeyChecking=no -i $SSH_PRIVATE_KEY $SSH_USERNAME@$SSH_HOST -p $SSH_PORT << EOF
  cd /home/nik/portfolios
  git pull
  python -m pip install --upgrade pip
  pip install -r requirements.txt
  sudo systemctl restart portfolios
  sudo systemctl restart celery
  sudo systemctl restart nginx
EOF

echo "Deployment completed!"
