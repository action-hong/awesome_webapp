#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2016-09-09 19:01:07
# @Author  : kkopite (kkopitehong@gmail.com)
# @Link    : kkopitehong.info
# @Version : 1.0

__author__ = 'kkopite'

' url handlers '


import re, time, json, logging, hashlib, base64, asyncio

import markdown2

from aiohttp import web

from coroweb import get, post
from apis import Page,APIValueError, APIResourceNotFoundError, APIPermissionError

from models import User, Comment, Blog, next_id
from config import configs

COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret

#返回值都是交给拦截器处理额,即response_factory

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')

def check_admin(request):
	if request.__user__ is None or not request.__user__.admin:
		raise APIPermissioinError()

def get_page_index(page_str):
	p = 1
	try:
		p = int(page_str)
	except ValueError as e:
		pass
	if p < 1:
		p = 1
	return p

@get('/register')
async def register():
	return {
		'__template__':'register.html'
	}

@get('/signin')
async def signin():
	return {
		'__template__':'signin.html'
	}

#一个转换而已,没有IO操作,还搞成aysnc
def user2cookie(user,max_age):
	'''
	Generate cookie str by user.
	'''
	#build cookie string by: id-expires-sha1
	expires = str(int(time.time() + max_age))
	s = '%s-%s-%s-%s' % (user.id,user.passwd,expires,_COOKIE_KEY)
	L = [user.id,expires,hashlib.sha1(s.encode('utf-8')).hexdigest()]
	return '-'.join(L)

#cookie:  uid-expires-sha1(三部分组成)
#由于需要数据库操作,所以异步
async def cookie2user(cookie_str):
	
	if not cookie_str:
		return None
	try:
		L = cookie_str.split('-')
		if len(L) != 3:
			return None
		uid,expires,sha1 = L

		#过期了
		if int(expires) < time.time():
			return None

		user = await User.find(uid)

		s = '%s-%s-%s-%s' % (uid,user.passwd,expires,_COOKIE_KEY)

		#判断是不是伪造的cookie,因为sha1这一串是服务器根据用户信息以及添加一些KEY生成的,不好伪造
		if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
			logging.info('invalid sha1')
			return None
		user.passwd = '******'
		return user
	except Exception as e:
		logging.exception(e)
		return None



@get('/')
async def index(request):
	summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elitsed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
	# blogs = [
	#     Blog(id='1', name='Test Blog', summary=summary, created_at=time.time()-120),
	#     Blog(id='2', name='Something New', summary=summary, created_at=time.time()-3600),
	#     Blog(id='3', name='Learn Swift', summary=summary, created_at=time.time()-7200)
	# ]
	blogs = await Blog.findAll(orderBy='created_at desc')
	# return dict(blogs=blogs)
	return {
		'__template__': 'blogs.html',
		'blogs': blogs
	}




@post('/api/authenticate')
async def authenticate(*,email,passwd):
	if not email:
		raise APIValueError('email','Invalid email')
	if not passwd:
		raise APIValueError('passwd','Invalid password.')
	users = await User.findAll('email=?',[email])
	if len(users) == 0:
		raise APIValueError('email','Email not exist')
	user = users[0]

	sha1 = hashlib.sha1()
	#check passwd
	sha1.update(user.id.encode('utf-8'))
	sha1.update(b':')
	sha1.update(passwd.encode('utf-8'))
	if user.passwd != sha1.hexdigest():
		raise APIValueError('passwd','Invalid password')

	#authenticate ok set cookie:
	r = web.Response()
	logging.info('%s,%s,%s' % (user.id,user.passwd,user.email))
	r.set_cookie(COOKIE_NAME,user2cookie(user,86400),max_age=86400,httponly=True)
	user.passwd = '******'
	r.content_type = 'application/json'
	r.body = json.dumps(user,ensure_ascii=False).encode('utf-8')
	return r


@get('/signout')
async def signout(request):
	referer = request.headers.get('Referer')
	r = web.HTTPFound(referer or '/')
	r.set_cookie(COOKIE_NAME,'-deleted-',max_age=0,httponly=True)
	logging.info('user sign out.')
	return r


@get('/blog/{id}')
async def get_blog(id):
	blog = await Blog.find(id)
	comments = await Comment.findAll('blog_id=?',[id],orderBy='created_at desc')
	for c in comments:
		c.html_content = text2html(c.content)
	return {
		'__template__':'blog.html',
		'blog':blog,
		'comments':comments
	}


@get('/api/blogs/{id}')
async def api_get_blogs(*,id):
	blog = await Blog.find(id)
	return blog

#---------------------------------管理页面--------------------------------------------

@get('/manage/comments')
async def manage_comments():
	pass

@get('/manage/blogs')
def manage_blogs(*,page='1'):
	return {
		'__template__':'manage_blogs.html',
		'page_index':get_page_index(page)
	}

@get('/manage/blogs/create')
async def manage_create_blog():
	return {
		'__template__':'manage_edit_blog.html',
		'id':'',
		'action':'/api/blogs'
	}


@get('/manage/blogs/edit')
async def manage_edit_blog(*,id):
	return {
		'__template__':'manage_edit_blog.html',
		'id':id,
		'action':'/api/blogs/%s' % id
	}


@get('/manage/users')
async def manage_users():
	pass	



#---------------------------------后端API--------------------------------------------
#---------------------------------后端API--------------------------------------------
#---------------------------------后端API--------------------------------------------

#获取日志
@get('/api/blogs')
async def api_blog(*,page='1'):
	page_index = get_page_index(page)
	num = await Blog.findNumber('count(id)')
	p = Page(num,page_index)
	if num == 0:
		return dict(page = p,blogs = ())
	blogs = await Blog.findAll(orderBy='created_at desc',limit=(p.offset,p.limit))
	return dict(page=p,blogs=blogs)

#创建日志
@post('/api/blogs')
async def api_create_blog(request,*,name,summary,content):
	check_admin(request)
	if not name or not name.strip():
		raise APIValueError('name','name connot be empty')
	if not summary or not summary.strip():
		raise APIValueError('summary','summary connot be empty')
	if not content or not content.strip():
		raise APIValueError('content','content connot be empty')
	blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image, name=name.strip(), summary=summary.strip(), content=content.strip())
	await blog.save()
	return blog

#更新日志
@post('/api/blogs/{id}')
async def api_update_blog(request,*,id,name,summary,content):
	check_admin(request)
	#明明是Blogs去找,为毛是变成user了?
	blog = await Blog.find(id)
	if not name or not name.strip():
		raise APIValueError('name','name connot be empty')
	if not summary or not summary.strip():
		raise APIValueError('summary','summary connot be empty')
	if not content or not content.strip():
		raise APIValueError('content','content connot be empty')
	blog.name = name.strip()
	blog.summary = summary.strip()
	blog.content = content.strip()
	await blog.update()
	return blog

#删除日志
@post('/api/blogs/{id}/delete')
async def api_delete_blog(id,request):
    check_admin(request)
    #这个id并没有取到呀
    blog = await Blog.find(id)
    await blog.remove()
    return dict(id=id)	
#获取评论
@get('/api/comments')
async def api_get_comments():
	pass

#创建评论
@post('/api/blogs/{id}/comments')
async def api_create_comments():
	pass

#删除评论
@post('/api/blogs/{comment_id}/delete')
async def api_delete_comment(*,comment_id):
	pass

#创建新用户
@post('/api/users')
async def api_register_user(*,email,name,passwd):
	if not name or not name.strip():
		raise APIValueError('name')
	if not email or not _RE_EMAIL.match(email):
		raise APIValueError('email')
	if not passwd or not _RE_SHA1.match(passwd):
		raise APIValueError('passwd')
	users = await User.findAll('email=?',[email])
	if len(users) > 0:
		raise APIValueError('register:failed','email','Email is already in use')
	uid = next_id()
	sha1_passwd = '%s:%s' % (uid,passwd)

	# 注意用户口令是客户端传递的经过SHA1计算后的40位Hash字符串，所以服务器端并不知道用户的原始口令。
	user = User(id=uid,name=name.strip(),email=email,passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(),image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
	await user.save()

	# make session cookie:
	r = web.Response()
	r.set_cookie(COOKIE_NAME,user2cookie(user,86400),max_age=86400,httponly=True)

	user.passwd = '******'
	r.content_type = 'application/json'
	r.body = json.dumps(user,ensure_ascii=False).encode('utf-8')
	return r

#获取用户
@get('/api/users')
async def api_get_users():
	users = await User.findAll(orderBy='created_at')
	for u in users:
		u.passwd = '******'
	#返回一个dict,user=>user的list
	return dict(users=users)

#---------------------------------后端API--------------------------------------------
#---------------------------------后端API--------------------------------------------
#---------------------------------后端API--------------------------------------------