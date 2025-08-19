#!/usr/bin/env bash
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate build
./build-env.sh 3.10
export PYTHON_VERSION="3.10" ; python conda_env_to_app.py settings.py --clear --build --dmg
./build-env.sh 3.11
export PYTHON_VERSION="3.11" ; python conda_env_to_app.py settings.py --clear --build --dmg
./build-env.sh 3.12
export PYTHON_VERSION="3.12" ; python conda_env_to_app.py settings.py --clear --build --dmg
./build-env.sh 3.13
export PYTHON_VERSION="3.13" ; python conda_env_to_app.py settings.py --clear --build --dmg