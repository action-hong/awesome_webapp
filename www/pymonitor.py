#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2016-09-10 17:30:01
# @Author  : kkopite (kkopitehong@gmail.com)
# @Link    : kkopitehong.info
# @Version : 1.0

__author__ = 'kkopite'

import os,sys,time,subprocess

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

def log(s):
	print('[Monitor] %s' %s)

class MyFileSystemEventHandler(FileSystemEventHandler):
	"""docstring for MyFileSystemEventHandler"""
	def __init__(self, fn):
		super(MyFileSystemEventHandler, self).__init__()
		self.restart = fn
		
	def on_any_event(self,event):
		if event.src_path.endswith('.py'):
			log('Python source file changed: %s' % event.src_path)
			self.restart()

command = ['echo','ok']
process = None

def kill_process():
	global process
	if process:
		log('kill process [%s}...' % process.pid)
		process.kill()
		process.wait()
		log('process ended with code %s.' % process.returncode)
		process = None

def start_process():
	global process,command
	log('start process %s...' % ' '.join(command))
	process = subprocess.Popen(command,stdin=sys.stdout,stderr=sys.stderr)

def restart_process():
	kill_process()
	start_process()

def start_watch(path,callback):
	observer = Observer()
	observer.schedule(MyFileSystemEventHandler(restart_process),path,recursive=True)
	observer.start()
	log('Wathcing directory %s...' % path)
	start_process()
	try:
		while True:
			time.sleep(5)
	except KeyboardInterrupt:
		observer.stop()
	observer.join()

if __name__ == '__main__':
	argv = sys.argv[1:]
	if not argv:
		print('Usage:./pymonitor your-script.py')
		exit(0)
	if argv[0] != 'python':
		argv.insert(0, 'python')
	command = argv
	path = os.path.abspath('.')
	start_watch(path, None)
