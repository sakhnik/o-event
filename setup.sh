#!/bin/bash

this_dir=$(dirname $(readlink -f ${BASH_SOURCE[0]}))
cd $this_dir

virtualenv venv
source venv/bin/activate
pip install -r requirements.txt

export PYTHONPATH=$this_dir
bash
