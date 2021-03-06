#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2016-09-08 22:43:18
# @Author  : kkopite (kkopitehong@gmail.com)
# @Link    : kkopitehong.info
# @Version : 1.0

__author__ = 'kkopite'

import time,uuid
import orm
from orm import Model, StringField, BooleanField, FloatField, TextField

def next_id():
	return '%015d%s000' % (int(time.time() * 1000), uuid.uuid4().hex)

class User(Model):

	__table__ = 'users'

	id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
	email = StringField(ddl='varchar(50)')
	passwd = StringField(ddl='varchar(50)')
	admin = BooleanField()
	name = StringField(ddl='varchar(50)')
	image = StringField(ddl='varchar(500)')
	created_at = FloatField(default=time.time)

class Blog(Model):
	__table__ = 'blogs'

	id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
	user_id = StringField(ddl='varchar(50)')
	user_name = StringField(ddl='varchar(50)')
	user_image = StringField(ddl='varchar(500)')
	name = StringField(ddl='varchar(50)')
	summary = StringField(ddl='varchar(200)')
	content = TextField()
	created_at = FloatField(default=time.time)

class Comment(Model):
	__table__ = 'comments'

	id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
	blog_id = StringField(ddl='varchar(50)')
	user_id = StringField(ddl='varchar(50)')
	user_name = StringField(ddl='varchar(50)')
	user_image = StringField(ddl='varchar(500)')
	content = TextField()
	created_at = FloatField(default=time.time)  

async def test(loop):
	await orm.create_pool(loop=loop,user='root',password='mobi0982',db='awesome')
	u = User(name='Bob', email='bob@example.com', passwd='1234567890', image='about:blank')
	u1 = User(name='Jane', email='jone@example.com', passwd='1234567890', image='about:blank')
	u2 = User(name='Chris', email='chris@example.com', passwd='1234567890', image='about:blank')
	await u.save()
	await u1.save()
	await u2.save()

def main():
	import asyncio
	loop = asyncio.get_event_loop()
	loop.run_until_complete(test(loop))
	if loop.is_closed():
		sys.exit(0)

if __name__ == '__main__':

	main()

