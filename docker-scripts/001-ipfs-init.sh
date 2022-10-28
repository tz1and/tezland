#!/bin/sh
set -ex
ipfs config --json API.HTTPHeaders.Access-Control-Allow-Origin '["*"]'
ipfs config --json Datastore.StorageMax '"10GB"'
ipfs config --json Datastore.GCPeriod '"1h"'
ipfs config --json Addresses.API '"/ip4/0.0.0.0/tcp/5001"'
ipfs config --json Addresses.Gateway '"/ip4/0.0.0.0/tcp/8080"'
ipfs config --json Addresses.Swarm '[ "/ip4/0.0.0.0/tcp/4001", "/ip6/::/tcp/4001", "/ip4/0.0.0.0/udp/4001/quic", "/ip6/::/udp/4001/quic" ]'