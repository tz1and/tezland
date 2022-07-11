#!/bin/sh
set -ex
ipfs config --json API.HTTPHeaders.Access-Control-Allow-Origin '["*"]'
ipfs config --json Datastore.StorageMax '"10GB"'
ipfs config --json Datastore.GCPeriod '"1h"'
