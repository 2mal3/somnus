#!/bin/sh

chown -R nonroot:nonroot /app/data
gosu nonroot python3 -m somnus