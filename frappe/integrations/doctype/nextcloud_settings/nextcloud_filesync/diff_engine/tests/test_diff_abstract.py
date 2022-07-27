import unittest

from frappe.integrations.doctype.nextcloud_settings.nextcloud_filesync.diff_engine.Action import (
	Action,  # type: ignore
)
from frappe.integrations.doctype.nextcloud_settings.nextcloud_filesync.diff_engine.DiffEngineTestable import (
	DiffEngineTest,
)
from frappe.integrations.doctype.nextcloud_settings.nextcloud_filesync.diff_engine.Entry import (
	EntryLocal,
	EntryRemote,
)


def using_test_differ(func):
	def wrapper(self: unittest.TestCase, *args, **kwargs):
		res = func(self, *args, **kwargs)

		all_local = list(res.get("l", []))
		all_remote = list(res.get("r", []))

		# for child in all_local:
		# 	if child.path == '/': continue
		# 	_, file_name = ('/' + child.path.strip('/')).rsplit('/', 1)
		# 	is_dir = child.path.endswith('/')
		# 	if is_dir:
		# 		file_name += '/'
		# 	for parent in all_local:
		# 		if parent.path.endswith('/'):
		# 			if child.path == parent.path + file_name:
		# 				# if parent.nextcloud_id is not None and child.parent_id is not None:
		# 				# 	print(child, parent)
		# 				# if parent.nextcloud_id is None and child.parent_id is not None:
		# 				# 	print('unlinked parent, weird but won’t cause bugs')
		# 				# 	print(child, parent)
		# 				# if parent.nextcloud_id is not None and child.parent_id is None:
		# 				# 	print('parent has nextcloud_id on local but child has no parent_id')
		# 				# 	print(child, parent)
		# 				# if parent.nextcloud_id is None and child.parent_id is None:
		# 				# 	print(child, parent)
		# 				if parent.nextcloud_id is not None\
		# 					and child.parent_id is not None\
		# 					and parent.nextcloud_id != child.parent_id:
		# 					print('parent.nextcloud_id != child.nextcloud_parent_id', child, parent)

		expected_actions = list(res.get("a", {}))

		if "diff_direction" in res:
			diff_direction = "fromRemote" if res.get("diff_direction") == "fromRemote" else "toRemote"
		else:
			diff_direction = "fromRemote" if res.get("kL", None) is None else "toRemote"

		use_conflict_detection = res.get("use_conflict_detection", None)

		self.differ = DiffEngineTest(use_conflict_detection=use_conflict_detection, logger=print)
		self.differ._test_init(all_local, all_remote)

		if diff_direction == "fromRemote":
			known_remote = list(res.get("kR", all_remote))
			it = self.differ.diff_from_remote(known_remote)
		else:
			known_local = list(res.get("kL", all_local))
			it = self.differ.diff_from_local(known_local)

		actions = list(it)
		if len(actions) != len(list(set(actions))):
			raise ValueError("Duplicate action in", actions)
		try:
			self.assertEqual(set(actions), set(expected_actions))
		except AssertionError:
			err = []
			err.append("Received Actions:" + (" EMPTY" if len(actions) == 0 else ""))
			for a in actions:
				err.append("- " + str(a))
			err.append("")
			err.append("Expected Actions:" + (" EMPTY" if len(expected_actions) == 0 else ""))
			for a in expected_actions:
				err.append("- " + str(a))
			err = "Action list is incorrect.\n" + "\n".join(err)
			raise AssertionError(err) from None
		return res

	return wrapper


class TestNCBaseDiffEngine(unittest.TestCase):
	@using_test_differ
	def test_file_created(self):
		L = [
			EntryLocal("/", "root1", 0, parent_id=None),
		]
		kR = [
			EntryRemote("/", "root2", 0, parent_id=None),  # etag changes on / because of file addition
			EntryRemote("/a", "β", 1, parent_id=0),
		]
		R = [*kR]
		expected = {
			Action("local.create", None, kR[1]),
			Action("meta.updateEtag", L[0], kR[0]),
		}
		return dict(l=L, r=R, kR=kR, a=expected)

	@using_test_differ
	def test_content_changed(self):
		L = [
			EntryLocal("/", "root1", 0, parent_id=None),
			EntryLocal("/a", "etag1", 1, parent_id=0),
		]
		kR = [
			EntryRemote("/", "root2", 0, parent_id=None),  # etag changes on / because of content change
			EntryRemote("/a", "etag2", 1, parent_id=0),  # etag changes on / because of content change
		]
		R = [*kR]
		expected = {
			Action("local.file.updateContent", L[1], kR[1]),
			Action("meta.updateEtag", L[0], kR[0]),
		}
		return dict(l=L, r=R, kR=kR, a=expected)

	@using_test_differ
	def test_rename1(self):
		L = [EntryLocal("/", "root1", 0, parent_id=None), EntryLocal("/a", "unchanged", 1, parent_id=0)]

		# etag changes on / because of file rename
		kR = [EntryRemote("/", "root2", 0, parent_id=None)]

		# /a is not known because it was not modified, just renamed
		R = [*kR, EntryRemote("/newname", "unchanged", 1, parent_id=0)]

		expected = {
			Action("local.file.moveRename", L[1], R[1]),
			Action("meta.updateEtag", L[0], R[0]),
		}
		return dict(l=L, r=R, kR=kR, a=expected)

	@using_test_differ
	def test_rename2(self):
		L = [
			EntryLocal("/", "root1", 0, parent_id=None),
			EntryLocal("/a", "unchanged", 1, parent_id=0),
			EntryLocal("/b", "unchanged", 2, parent_id=0),
		]
		kR = [
			# etag changes on / because of file rename
			EntryRemote("/", "root2", 0, parent_id=None),
		]

		# /a & /b are not known because not modified, just /b renamed
		R = [
			*kR,
			EntryRemote("/a", "unchanged", 1, parent_id=0),
			EntryRemote("/newname", "unchanged", 2, parent_id=0),
		]
		expected = {
			Action("local.file.moveRename", L[2], R[2]),
			Action("meta.updateEtag", L[0], R[0]),
		}
		return dict(l=L, r=R, kR=kR, a=expected)

	@using_test_differ
	def test_change_rename(self):
		L = [
			EntryLocal("/", "", 0, parent_id=None),
			EntryLocal("/dir/", "", 2, parent_id=0),
			EntryLocal("/dir/oldname", "", 3, parent_id=2),
			EntryLocal("/file", "", 1, parent_id=0),
		]
		R = [
			EntryRemote("/", "CHANGED", 0, parent_id=None),
			EntryRemote("/dir/", "CHANGED", 2, parent_id=0),
			EntryRemote("/dir/newname", "CHANGED", 3, parent_id=2),
			EntryRemote("/file", "", 1, parent_id=0),
		]
		kR = [R[0], R[1], R[2]]
		expected = {
			Action("local.file.updateContent", L[2], R[2]),
			Action("local.file.moveRename", L[2], R[2]),
			Action("meta.updateEtag", L[0], R[0]),
			Action("meta.updateEtag", L[1], R[1]),
		}
		return dict(l=L, r=R, kR=kR, a=expected)

	@using_test_differ
	def test_deep_rename(self):
		L = [
			EntryLocal("/", "", 0, parent_id=None),
			EntryLocal("/a/", "", 1, parent_id=0),
			EntryLocal("/a/b/", "", 2, parent_id=1),
			# EntryLocal('/a/b/c/', '', 3, parent_id=2),
			# EntryLocal('/a/b/c/d/', '', 4, parent_id=3),
		]
		R = [
			EntryRemote("/", "C", 0, parent_id=None),  # changed
			EntryRemote("/x/", "C", 1, parent_id=0),  # changed
			EntryRemote("/x/y/", "C", 2, parent_id=1),  # changed
			EntryRemote("/x/y/z/", "C", 3, parent_id=2),  # created
			EntryRemote("/x/y/z/k/", "", 4, parent_id=3),  # created
		]
		kR = R  # all changed or created
		expected = {
			Action("local.dir.moveRenamePlusChildren", L[1], R[1]),
			Action("local.dir.moveRenamePlusChildren", L[2], R[2]),
			# Action('local.dir.moveRenamePlusChildren', L[3], R[3]),
			# Action('local.dir.moveRenamePlusChildren', L[4], R[4]),
			Action("local.create", None, R[3]),
			Action("local.create", None, R[4]),
			Action("meta.updateEtag", L[0], R[0]),
			Action("meta.updateEtag", L[1], R[1]),
			Action("meta.updateEtag", L[2], R[2]),
		}
		return dict(l=L, r=R, kR=kR, a=expected)

	@using_test_differ
	def test_moves_and_renames(self):
		L = [
			EntryLocal("/", "", 0, parent_id=None),
			EntryLocal("/a/", "", 1, parent_id=0),
			EntryLocal("/BBB/", "", 2, parent_id=0),
			EntryLocal("/c/", "", 3, parent_id=0),
			EntryLocal("/DDD/", "", 4, parent_id=0),
		]
		R = [
			EntryRemote("/", "C", 0, parent_id=None),  # changed
			EntryRemote("/b/", "C", 1, parent_id=0),  # mv a->b
			EntryRemote("/b/a/", "", 2, parent_id=1),  # unchanged, mv b->b/a
			EntryRemote("/d/", "C", 3, parent_id=0),  # mv c->d
			EntryRemote("/d/c/", "", 4, parent_id=3),  # unchanged, mv d->d/c
		]
		kR = filter(lambda e: e.etag == "C", R)
		expected = {
			Action("local.dir.moveRenamePlusChildren", L[1], R[1]),
			Action("local.dir.moveRenamePlusChildren", L[2], R[2]),
			Action("local.dir.moveRenamePlusChildren", L[3], R[3]),
			Action("local.dir.moveRenamePlusChildren", L[4], R[4]),
			Action("meta.updateEtag", L[0], R[0]),
			Action("meta.updateEtag", L[1], R[1]),
			Action("meta.updateEtag", L[3], R[3]),
		}
		return dict(l=L, r=R, kR=kR, a=expected)

	@using_test_differ
	def test_repath(self):
		L = [
			EntryLocal("/", "", 0, parent_id=None),
			EntryLocal("/a/", "", 1, parent_id=0),
			EntryLocal("/a/b/", "", 2, parent_id=1),
			EntryLocal("/a/b/c/", "", 3, parent_id=2),
			EntryLocal("/a/b/c/d/", "", 4, parent_id=3),
		]
		R = [
			EntryRemote("/", "C", 0, parent_id=None),
			EntryRemote("/x/", "", 1, parent_id=0),
			EntryRemote("/x/b/", "", 2, parent_id=1),
			EntryRemote("/x/b/c/", "", 3, parent_id=2),
			EntryRemote("/x/b/c/d/", "", 4, parent_id=3),
		]
		kR = filter(lambda e: e.etag == "C", R)
		expected = {
			Action("meta.updateEtag", L[0], R[0]),
			# Action('meta.updateEtag', L[1], R[1]),
			# Action('meta.updateEtag', L[2], R[2]),
			# Action('meta.updateEtag', L[3], R[3]),
			Action("local.dir.moveRenamePlusChildren", L[1], R[1]),
			# Action('local.dir.moveRenamePlusChildren', L[2], R[2]),
			# Action('local.dir.moveRenamePlusChildren', L[3], R[3]),
			# Action('local.dir.moveRenamePlusChildren', L[4], R[4]),
		}
		return dict(l=L, r=R, kR=kR, a=expected)

	@using_test_differ
	def test_merge_local_file_with_no_nextcloud_id(self):
		L = [
			EntryLocal("/", "", 0, parent_id=None),
			# not linked, no parent
			EntryLocal("/a", "", None, parent_id=None),
		]
		R = [
			EntryRemote("/", "C", 0, parent_id=None),
			EntryRemote("/a", "", 1, parent_id=0),
		]
		kR = filter(lambda e: e.etag == "C", R)
		expected = {
			Action("meta.updateEtag", L[0], R[0]),
			Action("local.join", L[1], R[1]),
		}
		config = {"use_conflict_detection": False}
		return dict(l=L, r=R, kR=kR, a=expected, **config)

	@using_test_differ
	def test_merge_local_file_without_nextcloud_id_with_conflicts(self):
		L = [
			EntryLocal("/", "", 0, parent_id=None, last_updated=1),
			# not linked, no parent
			EntryLocal("/a", "", None, parent_id=None, last_updated=99),
		]
		R = [
			EntryRemote("/", "C", 0, parent_id=None, last_updated=1),
			EntryRemote("/a", "", 1, parent_id=0, last_updated=1),
		]
		kR = filter(lambda e: e.etag == "C", R)
		expected = {
			Action("meta.updateEtag", L[0], R[0]),
			Action("conflict.localIsNewer", L[1], R[1]),
			# Action('local.join', L[1], R[1]),
		}

		config = {"use_conflict_detection": True}
		return dict(l=L, r=R, kR=kR, a=expected, **config)

	@using_test_differ
	def test_detect_last_update_changes(self):
		L = [
			EntryLocal("/", "", 0, parent_id=None, last_updated=2),
		]
		R = [
			EntryRemote("/", "", 0, parent_id=None, last_updated=1),
		]
		kR = [R[0]]
		expected = {
			Action(type="conflict.localIsNewer", local=L[0], remote=R[0]),
		}
		config = {"use_conflict_detection": True}
		return dict(l=L, r=R, kR=kR, a=expected, **config)

	@using_test_differ
	def test_detect_conflict_when_inconsistent_file_type(self):
		"""detect conflict when file type (dir, file) is inconsistent"""
		L = [
			EntryLocal("/a", "", 0, parent_id=None, last_updated=1),
		]
		R = [
			EntryRemote("/a/", "", 0, parent_id=None, last_updated=1),
		]
		kR = [R[0]]
		expected = {
			Action(type="conflict.incompatibleTypesDirVsFile", local=L[0], remote=R[0]),
		}
		config = {"use_conflict_detection": True}
		return dict(l=L, r=R, kR=kR, a=expected, **config)

	@using_test_differ
	def test_file_replace_without_conflict_detection(self):
		L, R = map(
			list,
			zip(
				*[
					(
						# assuming that even the etag doesn't change,
						# we should still detect the file as a conflict
						EntryLocal("/fichier", "A", 1, parent_id=None, last_updated=1),
						EntryRemote("/fichier", "B", 2, parent_id=None, last_updated=2),
						# file id changed -----------^
					)
				]
			),
		)
		kR = [R[0]]
		expected = {
			Action(type="local.join", local=L[0], remote=R[0]),
		}
		config = {"use_conflict_detection": False}
		return dict(l=L, r=R, kR=kR, a=expected, **config)

	@using_test_differ
	def test_file_replace_with_conflict_detection(self):
		L, R = map(
			list,
			zip(
				*[
					(
						# assuming that even the etag doesn't change,
						# we should still detect the file as a conflict
						EntryLocal("/fichier", "A", 1, parent_id=None, last_updated=1),
						EntryRemote("/fichier", "B", 2, parent_id=None, last_updated=2),
						# file id changed -----------^
					)
				]
			),
		)
		kR = [R[0]]
		expected = {
			Action(type="conflict.differentIds", local=L[0], remote=R[0]),
			# Action(type='local.join', local=L[1], remote=R[1]),
		}
		config = {"use_conflict_detection": True}
		return dict(l=L, r=R, kR=kR, a=expected, **config)

	@using_test_differ
	def test_join_unlinked_dir_with_already_linked_children(self):
		L, R = map(
			list,
			zip(
				*[
					(
						EntryLocal("/", "r", 0, parent_id=None, last_updated=1),
						EntryRemote("/", "r", 0, parent_id=None, last_updated=1),
					),
					(
						# almost identical
						EntryLocal("/dir/", "d", None, parent_id=0, last_updated=1),
						# dir is not linked ----^^^^
						EntryRemote("/dir/", "d", 1, parent_id=0, last_updated=1),
					),
					(
						EntryLocal("/dir/alpha", "A", 2, parent_id=1, last_updated=1),
						EntryRemote("/dir/alpha", "A", 2, parent_id=1, last_updated=1),
					),
					(
						EntryLocal("/dir/beta", "B", 3, parent_id=1, last_updated=1),
						EntryRemote("/dir/beta", "B", 3, parent_id=1, last_updated=1),
					),
				]
			),
		)
		kR = [R[1]]
		expected = {
			Action(type="local.join", local=L[1], remote=R[1]),
		}
		config = {"use_conflict_detection": True}
		return dict(l=L, r=R, kR=kR, a=expected, **config)

	@using_test_differ
	def test_unicode_nfc_normalization(self):
		"""Unicode NFC/NFD normalization"""
		L, R = map(
			list,
			zip(
				*[
					(
						EntryLocal("/\u0041\u0300", "", None, None),
						EntryRemote("/\u00c0", "", 0, None),
					)
				]
			),
		)
		kR = R  # [R[1]]
		expected = {
			Action("local.join", L[0], R[0]),
		}
		config = {"use_conflict_detection": True}
		return dict(l=L, r=R, kR=kR, a=expected, **config)

	@using_test_differ
	def test_cross_rename_no_move(self):
		"""Cross-rename, move back"""
		L, R = map(
			list,
			zip(
				*[
					(
						EntryLocal("/CR/", "X", 0, None),
						EntryRemote("/CR/", "Y", 0, None),
					),
					(
						# cross-rename a -> b
						EntryLocal("/CR/a/", "x=3", 1, 0),
						EntryRemote("/CR/b/", "y=4", 1, 0),
					),
					(
						# cross-rename b -> a
						EntryLocal("/CR/b/", "y=4", 2, 0),
						EntryRemote("/CR/a/", "x=3", 2, 0),
					),
					(
						# move /CR/a/x (id=/0/1/3)
						#   -> /CR/a/x (id=/0/2/3)
						EntryLocal("/CR/a/x", "", 3, 1),
						EntryRemote("/CR/a/x", "", 3, 2),
					),
					(
						# move /CR/b/y (id=/0/2/4)
						#   -> /CR/b/y (id=/0/1/4)
						EntryLocal("/CR/b/y", "", 4, 2),
						EntryRemote("/CR/b/y", "", 4, 1),
					),
				]
			),
		)
		kR = [R[0]]
		expected = {
			Action("meta.updateEtag", L[0], R[0]),
			Action("local.dir.moveRenamePlusChildren", L[2], R[2]),
			Action("meta.updateEtag", L[2], R[2]),
			Action("local.file.moveRename", L[3], R[3]),
			Action("local.dir.moveRenamePlusChildren", L[1], R[1]),
			Action("meta.updateEtag", L[1], R[1]),
			Action("local.file.moveRename", L[4], R[4]),
		}
		config = {"use_conflict_detection": True}
		return dict(l=L, r=R, kR=kR, a=expected, **config)

	@using_test_differ
	def test_local_to_remote_do_nothing_if_nothing_changes(self):
		"""local->remote: do nothing if nothing changes"""
		L, R = map(
			list,
			zip(
				*[
					(
						EntryLocal("/", "", 0, parent_id=None, last_updated=1),
						EntryRemote("/", "", 0, parent_id=None, last_updated=1),
					),
					(
						EntryLocal("/fichier", "A", 1, parent_id=0, last_updated=1),
						EntryRemote("/fichier", "A", 1, parent_id=0, last_updated=1),
					),
				]
			),
		)
		kL = [L[1]]
		expected = set()
		config = {"use_conflict_detection": True, "diff_direction": "fromLocal"}
		return dict(l=L, r=R, kL=kL, a=expected, **config)

	@using_test_differ
	def test_local_to_remote_file_replace_with_conflict_detection_is_a_conflict(self):
		"""local->remote: file replace w/ conflict detection is a conflict"""
		l = EntryLocal("/x", "", 2, parent_id=0, last_updated=1)
		r = EntryRemote("/x", "", 1, parent_id=0, last_updated=1)
		expected = {Action("conflict.differentIds", l, r)}
		config = {"use_conflict_detection": True, "diff_direction": "fromLocal"}
		return dict(l=[l], r=[r], kL=[l], a=expected, **config)

	@using_test_differ
	def test_local_to_remote_file_replace_without_conflict_detection_is_a_join(self):
		"""local->remote: file replace w/out conflict detection is a join"""
		l = EntryLocal("/x", "", 2, parent_id=0, last_updated=1)
		r = EntryRemote("/x", "", 1, parent_id=0, last_updated=1)
		expected = {Action("remote.join", l, r)}
		config = {"use_conflict_detection": False, "diff_direction": "fromLocal"}
		return dict(l=[l], r=[r], kL=[l], a=expected, **config)

	@using_test_differ
	def test_local_to_remote_rename(self):
		"""local->remote: rename"""
		L, R = map(
			list,
			zip(
				*[
					(
						EntryLocal("/", "A", 0, parent_id=None, last_updated=1),
						EntryRemote("/", "B", 0, parent_id=None, last_updated=1),
					),
					(
						EntryLocal("/oldName", "", 1, parent_id=0, last_updated=1),
						EntryRemote("/newName", "", 1, parent_id=0, last_updated=1),
					),
				]
			),
		)
		kL = [L[1]]
		expected = {
			Action("remote.file.moveRename", L[1], R[1]),
		}
		config = {"use_conflict_detection": True, "diff_direction": "fromLocal"}
		return dict(l=L, r=R, kL=kL, a=expected, **config)
