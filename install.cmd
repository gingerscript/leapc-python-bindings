py -m pip install -r requirements.txt
py -m build leapc-cffi
py -m pip install leapc-cffi/dist/leapc_cffi-0.0.1.tar.gz
py -m pip install -e leapc-python-api