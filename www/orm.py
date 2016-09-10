#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2016-09-08 17:46:09
# @Author  : kkopite (kkopitehong@gmail.com)
# @Link    : kkopitehong.info
# @Version : 1.0

__author__ = 'kkopite'

import asyncio, logging
import sys
import aiomysql

# logging.basicConfig(level=logging.INFO)
def log(sql,args=()):
	logging.info('SQL: %s' % sql)


async def create_pool(loop,**kw):
	logging.info('cerate database connection pool...')
	global __pool
	__pool = await aiomysql.create_pool(
		host = kw.get('host','localhost'),
		port = kw.get('port',3306),
		user = kw['user'],
		password = kw['password'],
		db = kw['db'],
		charset = kw.get('charset','utf8'),                 #是utf8 不是utf-8啊啊啊啊啊啊啊啊啊啊
		autocommit = kw.get('autocommit',True),
		maxsize = kw.get('maxsize',10),
		minsize = kw.get('minsize',1),
		loop = loop
	)


#select `p_id`,`name`,`password` from user where `p_id` = ?   (sql)
async def select(sql,args,size=None):
	# log(sql,args)
	global __pool
	async with __pool.get() as conn:
		cur = await conn.cursor(aiomysql.DictCursor)
		await cur.execute(sql.replace('?','%s'), args or ())
		if size:
			rs = await cur.fetchmany(size)
		else:
			rs = await cur.fetchall()
		await cur.close()
		logging.info('rows returned:%s' % len(rs))
		return rs		

async def execute(sql,args,autocommit=True):
	# log(sql,args)
	async with __pool.get() as conn:
		if not autocommit:
			await conn.begin()
		try:
			async with conn.cursor(aiomysql.DictCursor) as cur:
				print(sql.replace('?','%s'))
				await cur.execute(sql.replace('?' , '%s'),args)
				affected = cur.rowcount
			if not autocommit:
				await conn.commit()
		except BaseException as e:
			if not autocommit:
				await conn.rollback()
			raise 
		return affected	

#返回num个?,逗号相连,插入数据时使用
def create_args_string(num):
	L = []
	for n in range(num):
		L.append('?')
	return ','.join(L)

class Field(object):

	def __init__(self,name,column_type,primary_key,default):
		self.name = name
		self.column_type = column_type
		self.primary_key = primary_key
		self.default = default

	def __str__(self):
		return '<%s,%s:%s>' % (self.__class__.__name__,self.column_type,self.name)

class StringField(Field):

	def __init__(self,name=None,primary_key=False,default=None,ddl='varchar(100)'):
		super().__init__(name,ddl,primary_key,default)

class BooleanField(Field):

	def __init__(self,name=None,primary_key=False,default=False,ddl='boolean'):
		super().__init__(name,ddl,primary_key,default)

class IntegerField(Field):

	def __init__(self,name=None,primary_key=False,default=0,ddl='bigint)'):
		super().__init__(name,ddl,primary_key,default)

class FloatField(Field):

	def __init__(self,name=None,primary_key=False,default=0.0,ddl='real'):
		super().__init__(name,ddl,primary_key,default)

class TextField(Field):

	def __init__(self,name=None,primary_key=False,default=None,ddl='text'):
		super().__init__(name,ddl,primary_key,default)


class ModelMetaclass(type):

	def __new__(cls,name,bases,attrs):
		if name == 'Model':
			return type.__new__(cls,name,bases,attrs)
		
		tableName = attrs.get('__table__',None) or name
		logging.info('found model : %s (table: %s)' % (name,tableName))

		#k->v,这里存入的是字段的信息,比如一开始的类属性
		#id = StringField(primary_key=True, default=next_id, ddl='varchar(50)'),
		#这里面有id的缺省值信息(default),但是我们要把这个值清理掉,因为后面的实例属性也有一个id属性,
		#这个是确定的值,所以我们把前面写的值存入__mappings__里面去,等之后自动填写的时候找到这个信息进行填充
		mappings = dict()           #存放每个列名的信息
		fields = []                 #除了primary key的字段,列表名
		primaryKey = None           #primarykey
		for k,v in attrs.items():
			if isinstance(v,Field):
				logging.info('found mapping:%s => %s' % (k,v))
				mappings[k] = v
				if v.primary_key:
					# 找到主键:
					if primaryKey:
						raise RuntimeError('Duplicate primary key for field : %s' % k)
					primaryKey = k
				else:
					#是字段的存进去,cl
					fields.append(k)

		if not primaryKey:
			raise RuntimeError('Primary key not found')

		for k in mappings.keys():
			#这些对应的字段是要放传入的实例对象的属性的数据的,不然会和类的属性冲突
			#这里是个蛋疼的地方呀
			attrs.pop(k)

		escaped_fields = list(map(lambda f: '`%s`' % f, fields)) #所有字段加上引号
		attrs['__mappings__'] = mappings    # 保存属性和列的映射关系
		attrs['__table__']    = tableName
		attrs['__primary_key__'] = primaryKey #属性名
		attrs['__fields__'] = fields #除主键外的属性名

		#假设当前表格是user,primary是p_id,其他两个字段是name,password

		#select `p_id`,`name`,`password` from user 
		attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey,','.join(escaped_fields),tableName)

		#insert into `user` (`name`,`password`,`p_id`) values(?,?,?)
		attrs['__insert__'] = 'insert into `%s` (%s,`%s`) values (%s)' % (tableName,','.join(escaped_fields),
			primaryKey,create_args_string(len(escaped_fields) + 1))

		#update `user` set `name`=? , `password` = ? where `p_id` = ?
		attrs['__update__'] = 'update `%s` set %s where `%s` = ?' % (tableName,','.join(map(lambda f : '`%s`=?' % (mappings.get(f).name or f),fields)),primaryKey)

		#delete from `user` where `p_id` = ?
		attrs['__delete__'] = 'delete from `%s` where `%s` = ?' % (tableName,primaryKey)
		return type.__new__(cls,name,bases,attrs)


class Model(dict,metaclass=ModelMetaclass):

	def __init__(self,**kw):
		super(Model,self).__init__(**kw)

	def __getattr__(self,key):
		try:
			return self[key]
		except KeyError as e:
			raise AttributeError(r"'Model' object has no attributes '%s'" % key)

	def __setattr__(self,key,value):
		self[key] = value

	def getValue(self,key):
		return getattr(self,key,None)

	#相当于自动填充功能,没有填的数据,检查一下是否有默认值,
	#有默认值的话自己填进去,没有的话就不管了
	#有填的话自然也不用管了
	def getValueOrDefault(self,key):
		value = getattr(self,key,None)
		if value is None:
			#这里是个大bug呀,你的
			field = self.__mappings__[key]
			if field.default is not None:
				value = field.default() if callable(field.default) else field.default
				logging.debug('using default value for %s : %s' % (key,str(value)))
				setattr(self,key,value)
		return value

	@classmethod
	async def findAll(cls,where=None,args=None,**kw):
		' find object by where clause'
		sql = [cls.__select__]
		if where:									#添加where查询
			sql.append('where')
			sql.append(where)
		if args is None:
			args = []
		orderBy = kw.get('orderBy',None)
		if orderBy:									#添加排序语句
			sql.append('order by')
			sql.append(orderBy)
		limit = kw.get('limit',None)
		if limit is not None:
			sql.append('limit')
			if isinstance(limit,int):				#limit为一个,即限定查找个数
				sql.append('?')          			#在sql添加limit的占位符?
				args.append(limit)       			#在args中多添加一个limit的值
			elif isinstance(limit,tuple) and len(limit) == 2:
				sql.append('?,?')					#limit是一个范围,提阿难啊两个占位符
				args.extend(limit)					#在args中添加limit的范围
			else:
				raise ValueError('Invalid limit value: %s' % str(limit))
		rs = await select(' '.join(sql),args)		#将sql中的值空格隔开,组成sql语句,执行
		# 返回对象
		return [cls(**r) for r in rs]				#实例每个查询结果,返回

	@classmethod
	async def findNumber(cls,selectField,where=None,args=None):
		' find number by select and where'
		sql = ['select %s _num_ from `%s`' % (selectField,cls.__table__)]
		if where:
			sql.append('where')
			sql.append(where)
		rs = await select(' '.join(sql),args,1)
		if len(rs) == 0:
			return None
		return rs[0]['_num_']

	@classmethod
	async def find(cls,pk):
		' find object by primary key. '
		rs = await select('%s where `%s` = ?' % (cls.__select__,cls.__primary_key__),[pk],1)
		if len(rs) == 0:
			return None
		return cls(**rs[0])

	async def save(self):
		args = list(map(self.getValueOrDefault,self.__fields__))
		args.append(self.getValueOrDefault(self.__primary_key__))
		rows = await execute(self.__insert__,args)
		if rows != 1:
			logging.warm('failed to insert record : affected rows: %s' % rows)

	async def update(self):
		args = list(map(self.getValue,self.__fields__))
		args.append(self.getValue(self.__primary_key__))
		rows = await execute(self.__update__,args)
		if rows != 1:
			logging.warm('failed to update by primary key : affected rows : %s' % rows)

	async def remove(self):
		args = [self.getValue(self.__primary_key__)]
		rows = await execute(self.__delete__,args)
		if rows != 1:
			logging.warm('failed to remove by primary key : affected rows: %s' % rows)



class User(Model):
	__table__ = 'user'

	id = IntegerField(primary_key=True)
	name = StringField()


async def test(loop):
	await create_pool(loop=loop,user='root',password='mobi0982',db='test')
	user_update = User(id=122131,name='kkopitekkopite')
	user_del = User(id=5)
	await user_update.update()
	await user_del.remove()

if __name__ == '__main__':

	loop = asyncio.get_event_loop()
	loop.run_until_complete(test(loop))
	if loop.is_closed():
		sys.exit(0)
	