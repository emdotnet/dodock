// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
import { get_version_timeline_content } from "./version_timeline_content_builder";

frappe.ui.form.NewTimeline = class {
	constructor(opts) {
		Object.assign(this, opts);
		this.doc_info = this.frm && this.frm.get_docinfo() || {};
		this.make();
	}

	make() {
		this.timeline_wrapper = $(`<div class="new-timeline">`);
		this.timeline_items_wrapper = $(`<div class="timeline-items">`);
		this.timeline_actions_wrapper = $(`
			<div class="timeline-actions">
				<div class="timeline-dot"></div>
			</div>
		`);

		this.timeline_wrapper.append(this.timeline_actions_wrapper);
		this.timeline_wrapper.append(this.timeline_items_wrapper);

		this.parent.replaceWith(this.timeline_wrapper);
		this.timeline_items = [];
		this.render_timeline_items();
		this.setup_timeline_actions();
	}

	refresh() {
		this.doc_info = this.frm.get_docinfo() || {};
		this.render_timeline_items();
	}

	setup_timeline_actions() {
		this.add_action_button(__('New Email'), this.compose_mail.bind(this));
	}

	add_action_button(label, action) {
		let action_btn = $(`<button class="btn btn-xs btn-default action-btn">${label}</button>`);
		action_btn.click(action);
		this.timeline_actions_wrapper.append(action_btn);
		return action_btn;
	}

	render_timeline_items() {
		this.timeline_items_wrapper.empty();
		this.timeline_items = [];
		this.prepare_timeline_contents();

		this.timeline_items.sort((item1, item2) => new Date(item1.creation) - new Date(item2.creation));
		this.timeline_items.forEach(this.add_timeline_item.bind(this));
	}

	prepare_timeline_contents() {
		this.timeline_items.push(...this.get_view_timeline_contents());
		this.timeline_items.push(...this.get_communication_timeline_contents());
		this.timeline_items.push(...this.get_comment_timeline_contents());
		this.timeline_items.push(...this.get_energy_point_timeline_contents());
		this.timeline_items.push(...this.get_version_timeline_contents());
		this.timeline_items.push(...this.get_share_timeline_contents());
		// attachments
		// milestones
	}

	get_user_link(user) {
		const user_display_text = (frappe.user_info(user).fullname || '').bold();
		return frappe.utils.get_form_link('User', user, true, user_display_text);
	}

	add_timeline_item(item) {
		let timeline_item = this.get_timeline_item(item);
		this.timeline_items_wrapper.prepend(timeline_item);
		return timeline_item;
	}

	get_timeline_item(item) {
		const timeline_item = $(`<div class="timeline-item">`);

		if (item.icon) {
			timeline_item.append(`
				<div class="timeline-indicator">
					${frappe.utils.icon(item.icon, 'md')}
				</div>
			`);
		} else if (item.timeline_indicator) {
			timeline_item.append(item.timeline_indicator);
		} else {
			timeline_item.append(`<div class="timeline-dot">`);
		}

		timeline_item.append(`<div class="timeline-content ${item.card ? 'frappe-card' : ''}">`);
		timeline_item.find('.timeline-content').append(item.content);
		if (!item.hide_timestamp && !item.card) {
			timeline_item.find('.timeline-content').append(`<div>${comment_when(item.creation)}</div>`);
		}
		return timeline_item;
	}

	get_view_timeline_contents() {
		let view_timeline_contents = [];
		(this.doc_info.views || []).forEach(view => {
			let view_content = `
				<div>
					<a href="${frappe.utils.get_form_link('View Log', view.name)}">
						${__("{0} viewed", [this.get_user_link(view.owner)])}
					</a>
				</div>
			`;
			view_timeline_contents.push({
				icon: 'view',
				creation: view.creation,
				content: view_content,
			});
		});
		return view_timeline_contents;
	}

	get_communication_timeline_contents() {
		let communication_timeline_contents = [];
		(this.doc_info.communications|| []).forEach(communication => {
			communication_timeline_contents.push({
				icon: 'mail',
				creation: communication.creation,
				card: true,
				content: this.get_communication_timeline_content(communication),
			});
		});
		return communication_timeline_contents;
	}

	get_communication_timeline_content(doc) {
		let communication_content =  $(frappe.render_template('timeline_message_box', { doc }));
		this.setup_reply(communication_content);
		return communication_content;
	}

	get_comment_timeline_contents() {
		let comment_timeline_contents = [];
		(this.doc_info.comments || []).forEach(comment => {
			comment_timeline_contents.push({
				icon: 'small-message',
				creation: comment.creation,
				card: true,
				content: this.get_comment_timeline_content(comment),
			});
		});
		return comment_timeline_contents;
	}

	get_comment_timeline_content(doc) {
		const comment_content = $(frappe.render_template('timeline_message_box', { doc }));
		this.setup_comment_actions(comment_content, doc);
	}

	get_version_timeline_contents() {
		let version_timeline_contents = [];
		(this.doc_info.versions || []).forEach(version => {
			const contents = get_version_timeline_content(version, this.frm);
			contents.forEach((content) => {
				version_timeline_contents.push({
					creation: version.creation,
					content: content,
				});
			});
		});
		return version_timeline_contents;
	}

	get_share_timeline_contents() {
		let share_timeline_contents = [];
		(this.doc_info.share_logs || []).forEach(share => {
			share_timeline_contents.push({
				creation: share.creation,
				content: share.content,
			});
		});
		return share_timeline_contents;
	}

	get_energy_point_timeline_contents() {
		let energy_point_timeline_contents = [];
		(this.doc_info.energy_point_logs || []).forEach(log => {
			let timeline_indicator = `
			<div class="timeline-indicator ${log.points > 0 ? 'appreciation': 'criticism'}">
				${log.points}
			<div>`;

			energy_point_timeline_contents.push({
				timeline_indicator: timeline_indicator,
				creation: log.creation,
				content: frappe.energy_points.format_form_log(log)
			});
		});
		return energy_point_timeline_contents;
	}

	setup_reply(communication_box) {
		let actions = communication_box.find('.actions');
		let reply = $(`<a class="action-btn reply">${frappe.utils.icon('reply', 'md')}</a>`).click(e => {
			this.compose_mail(true);
		});
		let reply_all = $(`<a class="action-btn reply-all">${frappe.utils.icon('reply-all', 'md')}</a>`).click(e => {
			this.compose_mail(true);
		});
		actions.append(reply);
		actions.append(reply_all);
	}

	compose_mail(is_a_reply=false) {
		const args = {
			doc: this.frm.doc,
			frm: this.frm,
			recipients: this.get_recipient(),
			is_a_reply: is_a_reply,
			title: is_a_reply ? __('Reply') : null,
		};

		if (this.frm.doctype === "Communication") {
			args.txt = "";
			args.last_email = this.frm.doc;
			args.recipients = this.frm.doc.sender;
			args.subject = __("Re: {0}", [this.frm.doc.subject]);
		} else {
			const comment_value = frappe.markdown(this.frm.comment_box.get_value());
			args.txt = strip_html(comment_value) ? comment_value : '';
		}
		new frappe.views.CommunicationComposer(args);
	}

	get_recipient() {
		if (this.frm.email_field) {
			return this.frm.doc[this.frm.email_field];
		} else {
			return this.frm.doc.email_id || this.frm.doc.email || "";
		}
	}

	setup_comment_actions(comment_wrapper, doc) {
		let edit_wrapper = $(`<div class="comment-edit-box">`).hide();
		let edit_box = this.make_editable(edit_wrapper);
		let content_wrapper = comment_wrapper.find('.content');

		edit_box.set_value(doc.content);

		edit_box.on_submit = (value) => {
			content_wrapper.empty();
			content_wrapper.append(value);
			edit_button.prop("disabled", true);
			edit_box.quill.enable(false);

			doc.content = value;
			this.update_comment(doc.name, value)
				.then(edit_button.toggle_edit_mode)
				.finally(() => {
					edit_button.prop("disabled", false);
					edit_box.quill.enable(true);
				});
		};

		content_wrapper.after(edit_wrapper);

		let edit_button = $(`<button class="btn btn-link action-btn">${__("Edit")}</a>`).click(() => {
			edit_button.edit_mode ? edit_box.submit() : edit_button.toggle_edit_mode();
		});

		edit_button.toggle_edit_mode = () => {
			edit_button.edit_mode = !edit_button.edit_mode;
			edit_button.text(edit_button.edit_mode ? __('Save') : __('Edit'));
			edit_wrapper.toggle(edit_button.edit_mode);
			content_wrapper.toggle(!edit_button.edit_mode);
		};

		comment_wrapper.find('.actions').append(edit_button);
		comment_wrapper.find('.actions').append(`<btn class="btn-link action-btn">${frappe.utils.icon('close', 'sm', 'close')}</btn>`);
	}

	make_editable(container) {
		return frappe.ui.form.make_control({
			parent: container,
			df: {
				fieldtype: 'Comment',
				fieldname: 'comment',
				label: 'Comment'
			},
			// mentions: this.get_names_for_mentions(),
			render_input: true,
			only_input: true,
			no_wrapper: true
		});
	}

	update_comment(name, content) {
		return frappe.xcall('frappe.desk.form.utils.update_comment', { name, content })
			.then(() => {
				frappe.utils.play_sound('click');
			});
	}

	get_last_email() {
		return;
	}
};