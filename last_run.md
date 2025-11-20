
Traceback (most recent call last):
  File "C:\Users\Alex\miniconda3\envs\Minecraft\lib\site-packages\urllib3\connectionpool.py", line 787, in urlopen
    response = self._make_request(
  File "C:\Users\Alex\miniconda3\envs\Minecraft\lib\site-packages\urllib3\connectionpool.py", line 534, in _make_request
    response = conn.getresponse()
  File "C:\Users\Alex\miniconda3\envs\Minecraft\lib\site-packages\urllib3\connection.py", line 516, in getresponse
    httplib_response = super().getresponse()
  File "C:\Users\Alex\miniconda3\envs\Minecraft\lib\http\client.py", line 1375, in getresponse
    response.begin()
  File "C:\Users\Alex\miniconda3\envs\Minecraft\lib\http\client.py", line 318, in begin
    version, status, reason = self._read_status()
  File "C:\Users\Alex\miniconda3\envs\Minecraft\lib\http\client.py", line 279, in _read_status
    line = str(self.fp.readline(_MAXLINE + 1), "iso-8859-1")
  File "C:\Users\Alex\miniconda3\envs\Minecraft\lib\socket.py", line 717, in readinto
    return self._sock.recv_into(b)
ConnectionResetError: [WinError 10054] An existing connection was forcibly closed by the remote host

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "C:\Users\Alex\miniconda3\envs\Minecraft\lib\site-packages\requests\adapters.py", line 644, in send
    resp = conn.urlopen(
  File "C:\Users\Alex\miniconda3\envs\Minecraft\lib\site-packages\urllib3\connectionpool.py", line 841, in urlopen
    retries = retries.increment(
  File "C:\Users\Alex\miniconda3\envs\Minecraft\lib\site-packages\urllib3\util\retry.py", line 474, in increment
    raise reraise(type(error), error, _stacktrace)
  File "C:\Users\Alex\miniconda3\envs\Minecraft\lib\site-packages\urllib3\util\util.py", line 38, in reraise
    raise value.with_traceback(tb)
  File "C:\Users\Alex\miniconda3\envs\Minecraft\lib\site-packages\urllib3\connectionpool.py", line 787, in urlopen
    response = self._make_request(
  File "C:\Users\Alex\miniconda3\envs\Minecraft\lib\site-packages\urllib3\connectionpool.py", line 534, in _make_request
    response = conn.getresponse()
  File "C:\Users\Alex\miniconda3\envs\Minecraft\lib\site-packages\urllib3\connection.py", line 516, in getresponse
    httplib_response = super().getresponse()
  File "C:\Users\Alex\miniconda3\envs\Minecraft\lib\http\client.py", line 1375, in getresponse
    response.begin()
  File "C:\Users\Alex\miniconda3\envs\Minecraft\lib\http\client.py", line 318, in begin
    version, status, reason = self._read_status()
  File "C:\Users\Alex\miniconda3\envs\Minecraft\lib\http\client.py", line 279, in _read_status
    line = str(self.fp.readline(_MAXLINE + 1), "iso-8859-1")
  File "C:\Users\Alex\miniconda3\envs\Minecraft\lib\socket.py", line 717, in readinto
    return self._sock.recv_into(b)
urllib3.exceptions.ProtocolError: ('Connection aborted.', ConnectionResetError(10054, 'An existing connection was forcibly closed by the remote host', None, 10054, None))   

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "C:\Users\Alex\Desktop\Projects\Coding\Minecraft_master\run_voyager.py", line 25, in <module>
    voyager.learn()
  File "C:\Users\Alex\Desktop\Projects\Coding\Minecraft_master\voyager\voyager.py", line 373, in learn
    self.env.reset(
  File "C:\Users\Alex\Desktop\Projects\Coding\Minecraft_master\voyager\env\bridge.py", line 195, in reset
    self.pause()
  File "C:\Users\Alex\Desktop\Projects\Coding\Minecraft_master\voyager\env\bridge.py", line 215, in pause
    res = requests.post(f"{self.server}/pause")
  File "C:\Users\Alex\miniconda3\envs\Minecraft\lib\site-packages\requests\api.py", line 115, in post
    return request("post", url, data=data, json=json, **kwargs)
  File "C:\Users\Alex\miniconda3\envs\Minecraft\lib\site-packages\requests\api.py", line 59, in request
    return session.request(method=method, url=url, **kwargs)
  File "C:\Users\Alex\miniconda3\envs\Minecraft\lib\site-packages\requests\sessions.py", line 589, in request
    resp = self.send(prep, **send_kwargs)
  File "C:\Users\Alex\miniconda3\envs\Minecraft\lib\site-packages\requests\sessions.py", line 703, in send
    r = adapter.send(request, **kwargs)
  File "C:\Users\Alex\miniconda3\envs\Minecraft\lib\site-packages\requests\adapters.py", line 659, in send
    raise ConnectionError(err, request=request)
requests.exceptions.ConnectionError: ('Connection aborted.', ConnectionResetError(10054, 'An existing connection was forcibly closed by the remote host', None, 10054, None))
