
#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2016-09-08 17:19:27
# @Author  : kkopite (kkopitehong@gmail.com)
# @Link    : kkopitehong.info
# @Version : 1.0

__author__ = 'kkopite'

import logging; logging.basicConfig(level=logging.INFO)

import asyncio, os, json, time
from datetime import datetime

from aiohttp import web
from jinja2 import Environment, FileSystemLoader

from config import configs

import orm
from coroweb import add_routes, add_static

from handlers import cookie2user, COOKIE_NAME

def init_jinjia2(app,**kw):
	logging.info('init jinja2...')
	options = dict(
		autoescape = kw.get('autoescape',True),
		block_start_string = kw.get('block_start_string','{%'),
		block_end_string = kw.get('block_end_string','%}'),
		variable_start_string = kw.get('variable_start_string','{{'),
		variable_end_string = kw.get('variable_end_string','}}'),
		auto_reload = kw.get('auto_reload',True)
	)
	path = kw.get('path',None)
	if path is None:
		path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'templates')
	logging.info('set jinja2 template path : %s' % path)
	env = Environment(loader=FileSystemLoader(path),**options)
	filters = kw.get('filters',None)
	if filters is not None:
		for name,f in filters.items():
			env.filters[name] = f
	app['__templating__'] = env


async def logger_factory(app,handler):
	async def logger(request):
		logging.info('Request: %s %s' % (request.method,request.path))

		return (await handler(request))
	return logger

async def data_factory(app,handler):
	async def parse_data(request):
		if request.method == 'POST':
			if request.content_type.startswith('application/json'):
				request.__data__ = await request.json()
				logging.info('request json: %s' % str(request.__data__))
			elif request.content_type.startswith('application/x-www-form-urlencoded'):
				request.__data__ = await request.post()
				logging.info('request from: %s' % str(request.__data__))
		return (await handler(request))
	return parse_data

#处理handlers的返回值
async def response_factory(app,handler):
	async def reponse(request):
		logging.info('Response handler')
		#为毛接收到的请求是空?
		r = await handler(request)
		if isinstance(r,web.StreamResponse):
			return r
		if isinstance(r,bytes):
			resp = web.Response(body = r)
			resp.content_type = 'application/octet-stream'
			return resp
		if isinstance(r,str):
			if r.startswith('redirect:'):
				return web.HTTPFound(r[9:])
			resp = web.Response(body=r.encode('utf-8'))
			resp.content_type = 'text/html;charset=utf-8'
			return resp
		if isinstance(r,dict):
			template = r.get('__template__')
			if template is None:
				#json格式输出,正常电脑是不知道怎么把实例对象转成json的,所以要传入default告诉电脑,而__dict__是用来存实例对象的属性的,就是一个dict
				resp = web.Response(body=json.dumps(r,ensure_ascii=False,default=lambda o : o.__dict__).encode('utf-8'))
				resp.content_type = 'application/json;charset=utf-8'
				return resp
			else:
				#把__user_-取出来
				r['__user__'] = request.__user__
				#加载模板文件,传递信息render(**r)将信息搞进去
				logging.info(r)
				resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
				resp.content_type = 'text/html;charset=utf-8'
				return resp
		if isinstance(r,int) and r >= 100 and r < 600:
			return web.Response(r)
		if isinstance(r,tuple) and len(r) == 2:
			t,m = r
			if isinstance(t,int) and t >= 100 and t < 600:
				return web.Response(t,str(m))

		#default
		resp = web.Response(body=str(r).encode('utf-8'))
		resp.content_type = 'text/plain;charset=utf-8'
		return resp

	return reponse

#使用拦截器在处理url之前,把cookie解析出来,就有用户咯,写完记得放到app的初始化语句去呀
async def auth_factory(app,handler):
	async def auth(request):
		logging.info('check user : %s %s' % (request.method,request.path))

		#设置这么一个__user__属性,因为后面的response.handler要把这个值给r,搞到jinja2的模板中
		request.__user__ = None
		#是cookies啊啊啊
		cookie_str = request.cookies.get(COOKIE_NAME)
		if cookie_str:
			user = await cookie2user(cookie_str)
			if user:
				logging.info('set current user : %s' % user.email)
				request.__user__ = user
		if request.path.startswith('/manage/') and (request.__user__ is None or not request.__user__.admin):
			return web.HTTPFound('/signin')
		return (await handler(request))
	return auth


def datetime_filter(t):
	delta = int(time.time() - t)
	if delta < 60:
		return u'1分钟前'
	if delta < 3600:
		return u'%s分钟前' % (delta//60)
	if delta < 86400:
		return u'%s分钟前' % (delta//3600)
	if delta < 604800:
		return u'%s分钟前' % (delta//86400)
	dt = datetime.fromtimestamp(t)
	return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)

def index(request):
	return web.Response(body=b'<h1>Awesome</h1>')

async def init(loop):
	# await orm.create_pool(loop=loop,host='127.0.0.1',port=3306,user='root',
	# 	password='mobi0982',db='awesome')
	await orm.create_pool(loop=loop,user='root',password='mobi0982',db='awesome')
	app = web.Application(loop=loop,middlewares=[
			logger_factory,auth_factory,response_factory
		])
	init_jinjia2(app,filters=dict(datetime=datetime_filter))
	add_routes(app,'handlers')
	# add_route(app,'handler.index')
	add_static(app)	
	srv = await loop.create_server(app.make_handler(),'127.0.0.1',9000)
	logging.info('server started at http://127.0.0.1:9000...')
	return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()
