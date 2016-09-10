#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2016-09-09 11:20:28
# @Author  : kkopite (kkopitehong@gmail.com)
# @Link    : kkopitehong.info
# @Version : 1.0

__author__ = 'kkopite'

import asyncio, os, inspect, logging, functools

from urllib import parse

from aiohttp import web

from apis import APIError


def get(path):
	'''
	Define decorator @get('/path') 
	'''
	def decorator(func):
		@functools.wraps(func)
		def wrapper(*args,**kw):
			return func(*args,**kw)
		wrapper.__method__ = 'GET'
		wrapper.__route__  = path
		return wrapper
	return decorator

def post(path):
	'''
	Define decorator @post('/path') 
	'''
	def decorator(func):
		@functools.wraps(func)
		def wrapper(*args,**kw):
			return func(*args,**kw)
		wrapper.__method__ = 'POST'
		wrapper.__route__  = path
		return wrapper
	return decorator

#POSITIONAL_ONLY      	位置参数
#POSITIONAL_OR_KEYWORD	位置参数或者命名关键字参数(如foo(a) 你可以foo(1)  or  foo(a=1))
#VAR_POSITIONAL			可变参数
#KEYWORD_ONLY			命名关键字参数
#VAR_KEYWORD			关键字参数


#获得没有默认值的命名关键字参数,即这些参数必须要填
def get_required_kw_args(fn):
	args = []
	# 获得函数参数信息
	params = inspect.signature(fn).parameters
	for name,param in params.items():
		#是命名关键字参数,而且没有默认值
		if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
			args.append(name)
	return tuple(args)

#获得命名关键字参数的元祖
def get_named_kw_args(fn):
	args = []
	params = inspect.signature(fn).parameters
	for name,param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY:
			args.append(name)
	return tuple(args)

#是否有命名关键字参数
def has_named_kw_args(fn):
	params = inspect.signature(fn).parameters
	for name,param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY:
			return True

#是否有关键字参数
def has_var_kw_args(fn):
	params = inspect.signature(fn).parameters
	for name,param in params.items():
		if param.kind == inspect.Parameter.VAR_KEYWORD:
			return True

#是否存在request参数,request参数必须是最后一个命名关键字参数
def has_request_arg(fn):
	sig = inspect.signature(fn)
	params = sig.parameters
	#request参数标记位
	found = False
	for name,param in params.items():
		if name == 'request':
			found = True
			continue
		#不是可变参数,不是命名关键字参数,不是关键字参数
		#感觉只要found就行了呀,后面有参数的参数类型没必要判断呀?
		#也不可能在一个命名关键字参数后加位置参数吧
		#必须验证,,不然用户直接在url多加点东西,覆盖你前面的keyword就不好了,当然加点位置参数之类的就不要紧
		if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
			raise ValueError('request parameter must be the last named parameter in function:%s%s' % (fn.__name__,str(sig)))

	#这里之前居然没有返回found,难怪后面request没有值,(后面的判断这里是false了,当然不会给赋值)
	#但是还没找到这个request的参数是在哪里赋值的
	#这个request就是直接在函数上写的呀 啊啊啊啊啊啊 index(request)
	return found

class RequestHandler(object):

	def __init__(self,app,fn):
		self._app = app
		self._func = fn         #返回值为web.response()的函数
		self._has_request_arg = has_request_arg(fn)
		self._has_var_kw_arg = has_var_kw_args(fn)
		self._has_named_kw_arg = has_named_kw_args(fn)
		self._named_kw_args = get_named_kw_args(fn)
		self._required_kw_args = get_required_kw_args(fn)

	async def __call__(self,request):
		kw = None
		#有keyword parameter
		if self._has_var_kw_arg or self._has_named_kw_arg or self._required_kw_args:
			if request.method == 'POST':
				#没有content-type
				if not request.content_type:
					return web.HTTPBadRequest('Missing Content-Type.')
				ct = request.content_type.lower()
				if ct.startswith('application/json'):
					params = await request.json()
					if not isinstance(params,dict):
						return web.HTTPBadRequest('JSON body must be object')
					kw = params
				elif ct.startwith('application/x-www-form-urlencoded') or ct.startwith('multipart/form-data'):
					params = await request.post()
					kw = dict(**params)
				else:
					#不支持的content-type
					return web.HTTPBadRequest('Unsupported Content-Type: %S' % request.content_type)
			if request.method == 'GET':
				#获取所有的get来的,xxx?id=1&name=kkopite,取出id,kkopite
				qs = request.query_string
				if qs:
					kw = dict()
					#The optional argument keep_blank_values is a flag indicating whether blank values in percent-encoded queries should be treated as blank strings. A true value indicates that blanks should be retained as blank strings. The default false value indicates that blank values are to be ignored and treated as if they were not included.
					#parse_qs的True表示将空值当做空字符串
					for k,v in parse.parse_qs(qs,True).items():
						kw[k] = v[0]
		if kw is None:
			#从path中找参数  如/manage/blogs/{id}/delete,就找出了id
			kw = dict(**request.match_info)
		else:
			#如果只有命名关键字参数
			if not self._has_var_kw_arg and self._named_kw_args:
				copy = dict()
				#将kw中所有非命名关键字参数的都过滤到
				for name in self._named_kw_args:
					if name in kw:
						copy[name] = kw[name]

				#太不注意了呀擦
				#把kw=copy写到if里面去了,难怪会没有接受到
				kw = copy

				#传入的参数的key和命名关键字参数名相同,抱一个警告
				for k,v in request.match_info.items():
					if k in kw:
						logging.warning('Duplicate arg name in named arg and args: %s' % k)
					#靠,这里又缩进到if里面了
					kw[k] = v


		#存在请求参数
		if self._has_request_arg:
			kw['request'] = request

		#检查必须填写的命名关键字参数是否都在kw中了,即是否有却填参数
		if self._required_kw_args:
			for name in self._required_kw_args:
				if not name in kw:
					logging.info('----------%s----------' %name)
					return web.HTTPBadRequest('Missing argument: %s' % name)

		#响应传入的参数
		logging.info('call with args: %s' % str(kw))
		try:
			r = await self._func(**kw)
			return r
		except APIError as e:
			return dict(error = e.error,data = e.data,message=e.message)

#用于处理静态文件
def add_static(app):
	path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'static')
	app.router.add_static('/static/',path)
	logging.info('add static %s => %s' % ('/static/',path))

#添加一个处理fn的请求
def add_route(app,fn):
	method = getattr(fn,'__method__',None)
	path = getattr(fn,'__route__',None)
	if path is None or method is None:
		raise ValueError('@get or @post not defined in %s.' % str(fn))
	if not asyncio.iscoroutinefunction(fn) and not inspect.iscoroutinefunction(fn):
		fn = asyncio.coroutine(fn)
	logging.info('add route %s %s => %s(%s)' % (method,path,fn.__name__,','.join(inspect.signature(fn).parameters.keys())))
	
	#添加一个处理某个url的请求
	#如果参数是('GET','/test',RequestHandler(app,fn))
	app.router.add_route(method,path,RequestHandler(app,fn))

# 自动把handler模块的所有符合条件的函数注册了:
# add_routes(app, 'handlers')
# 
# 如下列这样
# add_route(app, handles.index)
# add_route(app, handles.blog)
# add_route(app, handles.create_comment)
def add_routes(app,module_name):
	#找有没有'.''
	n = module_name.rfind('.')
	if n == (-1):
		# 没找到
		mod = __import__(module_name,globals(),locals())
	else:
		name = module_name[n+1:]
		mod = getattr(__import__(module_name[:n],globals(),locals(),[name]),name)
	for attr in dir(mod):
		if attr.startswith('_'):
			#私有方法,不添加
			continue
		fn = getattr(mod,attr)
		if callable(fn):
			method = getattr(fn,'__method__',None)
			path = getattr(fn,'__route__',None)
			if method and path:
				add_route(app,fn)




