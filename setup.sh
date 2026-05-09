#!/bin/bash
# Knidos Daily Bot — Quick Setup Script

echo "Installing dependencies..."
pip install -r requirements.txt

if [ ! -f keys.txt ]; then
    echo ""
    echo "keys.txt not found. Creating template..."
    cat > keys.txt << 'EOF'
# Add your private keys below — one per line
# Lines starting with # are ignored
# Example:
# 0xabc123def456...
EOF
    echo "keys.txt created. Add your private keys before running."
fi

echo ""
echo "Setup complete. Run with: python3 bot.py"
