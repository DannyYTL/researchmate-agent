#!/bin/bash
# ResearchMate Setup Script

echo "🔬 ResearchMate Setup"
echo "===================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "✓ Python $python_version"
echo ""

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
echo "✓ pip upgraded"
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
echo "✓ Dependencies installed"
echo ""

# Setup .env file
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✓ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your API keys:"
    echo "   - OPENROUTER_API_KEY (get free key at https://openrouter.ai/keys)"
    echo "   - ANTHROPIC_API_KEY (optional, for Claude fallback)"
else
    echo "✓ .env file already exists"
fi
echo ""

# Create output directories
mkdir -p outputs reports checkpoints
echo "✓ Output directories created"
echo ""

echo "="
echo "Setup complete! Next steps:"
echo ""
echo "1. Activate the virtual environment:"
echo "   source venv/bin/activate"
echo ""
echo "2. Add your API keys to .env file"
echo ""
echo "3. Test the setup:"
echo "   python examples/test_llm_client.py"
echo ""
echo "4. Check the README.md for usage examples"
echo ""
