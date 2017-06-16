# awesome-webapp


增加了xx_factory后别忘了加入到middlewares中
app.py中：
app = web.Application(loop=loop, middlewares=[
		logger_factory, auth_factory, response_factory
	])

SQL语句出错是，检测一下是否封装的时候粗心了（其实是早起测试工作没做）
例如：orm.py在封装该功能时把 %s 错打成了 %a....
@classmethod
	async def findNumber(cls, selectField, where=None, args=None):
		' find number by select and where. '
		sql = ['select %s _num_ from `%s`' % (selectField, cls.__table__)]
		if where:
			sql.append('where')
			sql.append(where)
		rs = await select(' '.join(sql), args, 1)
		if len(rs) == 0:
			return None
		return rs[0]['_num_']


