# Voyager Installation Guide

## Fixed Dependency Issues

The original Voyager project had dependency conflicts between old LangChain versions (requiring Pydantic v1) and newer packages (requiring Pydantic v2). This has been resolved by pinning compatible versions.

## Installation Steps

### 1. Remove Existing Installation (Clean Slate)

```bash
# Deactivate any active conda environment first
conda deactivate

# Remove old environment if it exists
conda env remove -n voyager

# Create fresh conda environment
conda create -n voyager python=3.9 -y
conda activate voyager
```

### 2. Install Dependencies

```bash
# Navigate to Voyager directory
cd "C:\Users\Alex\OneDrive - Naval Postgraduate School\Desktop\Classes\Projects\Coding\Minecraft\Voyager"

# Install requirements with pinned versions
pip install --upgrade pip
pip install -r requirements.txt

# Install Voyager in development mode
pip install -e .
```

### 3. Install Node.js Dependencies (for Mineflayer)

```bash
# Navigate to mineflayer directory
cd voyager/env/mineflayer

# Install Node.js packages
npm install

# Return to project root
cd ../../../
```

### 4. Verify Installation

```bash
# Check that imports work
python -c "from voyager import Voyager; print('Voyager imported successfully!')"

# Check LangChain version
python -c "import langchain; print(f'LangChain version: {langchain.__version__}')"

# Check Pydantic version
python -c "import pydantic; print(f'Pydantic version: {pydantic.__version__}')"
```

## Expected Versions

After installation, you should have:
- **Python**: 3.9.x
- **LangChain**: 0.1.20
- **LangChain-OpenAI**: 0.0.8
- **LangChain-Community**: 0.0.38
- **Pydantic**: 1.10.x (NOT 2.x)
- **ChromaDB**: 0.4.24
- **OpenAI**: 1.12.0

## Code Changes Made

The following files were updated to use newer LangChain import paths:

1. `voyager/agents/action.py` - Updated ChatOpenAI import
2. `voyager/agents/skill.py` - Updated ChatOpenAI, OpenAIEmbeddings, Chroma imports
3. `voyager/agents/curriculum.py` - Updated ChatOpenAI, OpenAIEmbeddings, Chroma imports
4. `voyager/agents/critic.py` - Updated ChatOpenAI import

**Old imports (deprecated):**
```python
from langchain.chat_models import ChatOpenAI
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Chroma
```

**New imports (LangChain 0.1.x):**
```python
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
```

## Troubleshooting

### If you still see dependency conflicts:

1. **Clear pip cache:**
   ```bash
   pip cache purge
   ```

2. **Reinstall with no-cache:**
   ```bash
   pip install --no-cache-dir -r requirements.txt
   ```

3. **Check for conflicting packages:**
   ```bash
   pip list | grep -E "langchain|pydantic"
   ```

4. **If `langchain-classic` or `langchain-core 1.x` appear, uninstall them:**
   ```bash
   pip uninstall langchain-classic langchain-core langchain-text-splitters -y
   pip install -r requirements.txt
   ```

### Common Issues

**Issue: `ImportError: cannot import name 'ChatOpenAI'`**
- Solution: Make sure you have `langchain-openai==0.0.8` installed

**Issue: ChromaDB errors**
- Solution: Delete the vectordb directory and let it rebuild:
  ```bash
  rm -rf ckpt/*/vectordb
  ```

**Issue: Pydantic v2 is installed**
- Solution: Force install Pydantic v1:
  ```bash
  pip install "pydantic>=1.10.0,<2.0.0" --force-reinstall
  ```

## Next Steps

After successful installation, you can run Voyager:

```python
from voyager import Voyager

# Load OpenAI API key
with open("openAIKey.txt", "r") as f:
    openai_api_key = f.read().strip()

# Create Voyager instance (connects to LAN server)
voyager = Voyager(
    mc_host="10.0.132.101",  # Your homelab server
    mc_port=25565,
    openai_api_key=openai_api_key,
)

# Start learning
voyager.learn()
```
