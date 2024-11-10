case $1 in
"format")
   	python -m black .
	;;
"pdf")
	export PARSER_URL="0.0.0.0" 
	export PARSER_PORT="50058"
	export MINIO_ENDPOINT="localhost:9000"
	export MINIO_ACCESS_KEY="minioadmin"
	export MINIO_SECRET_KEY="minioadmin"
	python main.py
	;;
"build")
	cd rpc
	python3 -m grpc_tools.protoc \
	-I ../protos --python_out=.  \
	--pyi_out=. --grpc_python_out=. ../protos/file_parser.proto 
	;;
esac
