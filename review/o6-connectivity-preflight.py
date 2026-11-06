import socket,time
s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('192.168.0.35',8080));s.listen(4);s.settimeout(35)
print('PRIVATE_PREFLIGHT_READY',flush=True)
end=time.time()+35
while time.time()<end:
 try:c,a=s.accept()
 except socket.timeout:break
 with c:
  if a[0]=='192.168.0.7':
   c.sendall(b'LAB3_PRIVATE_CONNECTIVITY_OK\n');print('SECOND_HOST_CONNECTED',flush=True);break
s.close()
