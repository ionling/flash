#!/usr/bin/env bash

for f in $(ls $(dirname $0)/../*/.flash); do
    git mv $f $f.toml
done
