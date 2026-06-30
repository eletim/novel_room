#!/bin/bash

# ループバックインターフェースからの接続を許可
sudo iptables -A INPUT -i lo -j ACCEPT

# 192.168.1.0/24 ネットワークからのポート5000への接続を許可
sudo iptables -A INPUT -s 192.168.1.0/24 -p tcp --dport 5000 -j ACCEPT

# Tailscaleからの接続を許可
sudo iptables -A INPUT -s 100.105.193.17 -p tcp --dport 5000 -j ACCEPT

# 他のすべての接続を拒否（ポート5000に対してのみ）
sudo iptables -A INPUT -p tcp --dport 5000 -j REJECT

# Flaskサーバーを起動
python3 app.py
