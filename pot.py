#!/usr/bin/python
# -*- coding: utf-8 -*-

import ConfigParser
import datetime, struct, socket, time, math, array, re, sys, os
import mechanize

from twisted.internet.protocol import Protocol, ClientFactory
from twisted.internet import reactor, task
from gzip import GzipFile
from StringIO import StringIO
sys.path.append(os.path.abspath(os.path.dirname(sys.executable)))

stored = False

default_config = """
[settings]
debug = False

[remote]
host = example.com
port = 25565
username = foo
password = bar
"""

""" ********************************************************************* """
""" MinecraftBot """
class MinecraftBot:
    def __init__(self):
        self.reset()

        try:
            self.mainloop()
        except Exception, e:
            self.log_exception("__init__() -> mainloop()", e)
        except socket.error, se:
            self.log_exception("__init__()", se)
        except KeyboardInterrupt:
            self.log('Ctrl-C? Really! Maaaaaan...')
            self.server_stdin.write('stop\n')
            self.server.wait()

        self.log('Exit!')

    def reset(self):
        self.log('Starting Minecraftbot')
        #self.log('system: %s %s' % (sys.platform, sys.version))

        if not self.load_config():
            self.log('Failed loading the configuration file, this is fatal.')
            exit()
        else:
            self.dlog('Loaded configuration!')

    def log(self, msg):
        print '%s [BOT] %s' % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)

    def dlog(self, msg):
        if self.debug:
            print '%s [BOT] %s' % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)

    def log_exception(self, function, exception):
        self.log(' *** Exception %s in %s' % (exception,function))

    def load_config(self):
        try:
            config = ConfigParser.ConfigParser()
            config.readfp(StringIO(default_config))
        except ConfigParser.Error, cpe:
            self.log_exception('load_config()', cpe)
            return False

        if os.path.isfile('bot.ini'):
            self.dlog('Found configuration, loading...')

            try:
                config.read('bot.ini')
            except ConfigParser.Error, cpe:
                self.log_exception('load_config()', cpe)
                return False
        else:
            self.dlog('Could not find an existing configuration, creating it...')

            try:
                config_file = open('bot.ini', 'w')
                config.write(config_file)
            except Exception, e:
                self.log_exception('load_config()', e)
                return False
            finally:
                config_file.close()

        try:
            self.host = config.get('remote', 'host')
            self.port = config.getint('remote', 'port')
            self.username = config.get('remote', 'username')
            self.password = config.get('remote', 'password')
            self.address = (self.host, self.port)
            self.loading_map    = True
            
            self.debug = True
            self.name = ''
            self.sessionid = ''
            self.ticket = ''
            self.serverhash = ''

        except Exception, e:
            self.log_exception('load_config()', e)
            return False

        return True

    def onServerJoin(self, version, srv_name, motd, user_type):
        self.log("Joined server! Ver: %s, Name: %s, Motd: %s, Your type: %s"%(version,srv_name,motd,user_type))

    def getversion(self):
        login = mechanize.Browser()

        self.dlog('Going online')
        login.open("http://minecraft.net/login.jsp")
        login.select_form("input")
        login["username"] = self.username
        login["password"] = self.password
        login.submit()
        response = login.open("http://www.minecraft.net/game/getversion.jsp?user=%s&password=%s&version=%s" % (self.username, self.password, 11)).read().splitlines()

        for x in response:
            parts = x.split(":")
            self.version = parts[0]
            self.ticket = parts[1]
            self.name = parts[2]
            self.sessionid = parts[3]
            
        self.dlog("Version: %s, Ticket: %s, Name: %s, Session: %s" % (self.version, self.ticket, self.name, self.sessionid))
        
    def get_latest_clientjar(self):
        self.log("Checking for new version")
        clientdownload = mechanize.Browser()
        clientcheck = clientdownload.open("http://minecraft.net/game/minecraft.jar?user=%s&ticket=%s" % (self.username, self.ticket)).read().splitlines()

    def login(self):
        self.dlog('Authenticating with %s:%s (%s)' % (self.host, self.port, socket.gethostbyname(self.host)) );
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except Exception, e:
            self.log_exception('s.socket', e)

        try:
            s.connect((socket.gethostbyname(self.host), self.port))
        except Exception, e:
            self.log_exception(socket.error(), e)
       
        handshake = ''        
        handshake += struct.pack('b', 0x02) ## packet type
        handshake += struct.pack('b', 0x00) ## length of ... 
        handshake += struct.pack('b', 0x08) ## ...
        handshake += self.name              ## name
        #self.log(handshake)
        data = s.send(handshake)
        #self.log('Sent %s %s' % (repr(data), repr(handshake)))
        
        s.recv(4096)
        data = s.recv(4096)
        pieces = [data[i:i+2] for i in range(0, len(data), 2)]
        pieces.pop(0)
        self.serverid = "".join(pieces)
        
        loginurl = "http://www.minecraft.net/game/joinserver.jsp?user=%s&sessionId=%s&serverId=%s" %(self.username, self.sessionid, self.serverid)
        login = mechanize.Browser()

        self.dlog("Logging in to %s" % loginurl)
        data = login.open(loginurl)
        
        """
        for x in data:
            print(x)
        """

        authurl = "http://www.minecraft.net/game/checkserver.jsp?user=%s&serverId=%s" % (self.username, self.serverid)
        data2 = login.open(loginurl)
        """
        for y in data2:
            print(y)
        """
        
        login_packet = ''        
        login_packet += struct.pack('b', 0x01) ## packet type
        login_packet += struct.pack('b', 0x00) ## protocol version: 1 
        login_packet += struct.pack('b', 0x00) ##  
        login_packet += struct.pack('b', 0x00) ##  
        login_packet += struct.pack('b', 0x01) ## 
        login_packet += struct.pack('b', 0x00) ## length of ... 
        login_packet += struct.pack('b', 0x08) ## ...
        login_packet += self.name              ## name
        login_packet += struct.pack('b', 0x00) ## length of ... 
        login_packet += struct.pack('b', 0x08) ## ... 
        login_packet += 'Password'              ## name
        
        data = s.send(login_packet)
        s.recv(4096);
        self.dlog('Sent %s %s' % (repr(data), repr(login_packet)))

        while True:
            ping = struct.pack('b', 0x00)
            s.send(ping)
            data = s.recv(4096)
            pieces = [data[i:i+1] for i in range(0, len(data), 1)]
            self.dlog("Data: %s" % pieces)
            self.log('S: %s - R: %s' % (repr(ping), data))
            time.sleep(20)

        s.close()

    def mainloop(self):
        self.getversion()
        self.login()
            
if __name__ == '__main__':
    bot = MinecraftBot()