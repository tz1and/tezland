needs latest bcdhub with hangzhou support. bump version and build local with

 make stable-images

acces control stuff for ipfs

 COMPOSE_PROJECT_NAME=bcdbox docker-compose exec ipfs ipfs config --json API.HTTPHeaders.Access-Control-Allow-Origin '["*"]'
