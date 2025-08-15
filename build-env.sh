#!/bin/bash

# Source conda initialization
source $HOME/miniconda3/etc/profile.d/conda.sh

# Now conda commands will work
conda env remove -n opensesame -y
conda create -n opensesame python=3.13 -y
conda activate opensesame
pip install -r requirements.txt
pip install psychopy --ignore-requires-python --no-deps
pip install psychopy_sounddevice psychopy_visionscience