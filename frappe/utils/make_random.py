from __future__ import unicode_literals
import frappe, random
from six.moves import range
from six import string_types

settings = frappe._dict(
	prob = {
		"default": { "make": 0.6, "qty": (1,5) },
	}
)

def add_random_children(doc, fieldname, rows, randomize, unique=None):
	nrows = rows
	if rows > 1:
		nrows = random.randrange(1, rows)

	for i in range(nrows):
		d = {}
		valid_child = True
		for key, val in randomize.items():
			if isinstance(val[0], string_types):
				d[key] = get_random(*val)
			else:
				d[key] = random.randrange(*val)

			if d[key] is None:
				valid_child = False
				break

		if valid_child and unique:
			if not doc.get(fieldname, {unique:d[unique]}):
				doc.append(fieldname, d)
		elif valid_child:
			doc.append(fieldname, d)

def get_random(doctype, filters=None, doc=False):
	from frappe.desk.reportview import get_filters_cond
	condition = []
	if filters:
		get_filters_cond(doctype, filters, condition, ignore_permissions=True)

	if condition:
		condition = " where " + " and ".join(condition)
	else:
		condition = ""

	out = frappe.db.sql("""select name from `tab%s` %s
		order by RAND() limit 0,1""" % (doctype, condition))

	out = out and out[0][0] or None

	if doc and out:
		return frappe.get_doc(doctype, out)
	else:
		return out

def can_make(doctype):
	return random.random() < settings.prob.get(doctype, settings.prob["default"])["make"]

def how_many(doctype):
	return random.randrange(*settings.prob.get(doctype, settings.prob["default"])["qty"])
