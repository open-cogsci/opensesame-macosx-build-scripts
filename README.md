# OpenSesame buld scripts for Mac OSX

These scripts package an Anaconda environment with OpenSesame installed into a `.dmg` package.

## Dependencies

- python-magic (requires libmagic to be separately installed)
- biplist
- six
- dmgbuild

## Usage

First create an anaconda, or actually miniconda, environment. This should be located in `/Users/[username]/miniconda3/envs/opensesame`.

```
conda create -n opensesame python=3.13
conda activate opensesame
pip install -r requirements.txt
pip install psychopy --ignore-requires-python --no-deps
conda deactivate
```

Next, run the packaging script to build a `.dmg` package.

```
export PYTHON_VERSION="3.10" ; python conda_env_to_app.py settings.py --clear --build --dmg
````

