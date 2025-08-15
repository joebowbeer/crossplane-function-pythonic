#!/usr/bin/env bash
cd $(dirname $(realpath $0))
PYTHONPATH=$PWD exec hatch run development
