import Quill from 'quill';
import TemplateFieldSelector from './template_field_selector';

// replace <p> tag with <div>
const Block = Quill.import('blots/block');
Block.tagName = 'DIV';
Quill.register(Block, true);

const CodeBlockContainer = Quill.import('formats/code-block-container');
CodeBlockContainer.tagName = 'PRE';
Quill.register(CodeBlockContainer, true);

// table
const Table = Quill.import('formats/table-container');
const superCreate = Table.create.bind(Table);
Table.create = (value) => {
	const node = superCreate(value);
	node.classList.add('table');
	node.classList.add('table-bordered');
	return node;
}
Quill.register(Table, true);

// Template blot
const ATTRS = {
	PARENT: 'data-doctype',
	FIELDNAME: 'data-value',
	REFERENCE: 'data-reference',
	LABEL: 'data-label',
	FUNCTION: 'data-function'
};

const Embed = Quill.import('blots/embed');

class TemplateBlot extends Embed {
	static create(value) {
		let node = super.create(value);
		node.setAttribute('class', 'badge');
		node.setAttribute(ATTRS.PARENT, value.parent);
		node.setAttribute(ATTRS.FIELDNAME, value.fieldname);
		node.setAttribute(ATTRS.REFERENCE, value.reference);
		node.setAttribute(ATTRS.LABEL, value.label);
		node.setAttribute(ATTRS.FUNCTION, value.function);
		node.innerHTML = value.label;
		return node;
	}

	static value(node) {
		return {
			parent: node.getAttribute(ATTRS.PARENT),
			fieldname: node.getAttribute(ATTRS.FIELDNAME),
			reference: node.getAttribute(ATTRS.REFERENCE),
			label: node.getAttribute(ATTRS.LABEL),
			function: node.getAttribute(ATTRS.FUNCTION)
		};
	}
}
TemplateBlot.blotName = 'template-blot';
TemplateBlot.tagName = 'template-blot';

Quill.register({
	'formats/template-blot': TemplateBlot
});

// image uploader
const Uploader = Quill.import('modules/uploader');
Uploader.DEFAULTS.mimetypes.push('image/gif');

// inline style
const BackgroundStyle = Quill.import('attributors/style/background');
const ColorStyle = Quill.import('attributors/style/color');
const SizeStyle = Quill.import('attributors/style/size');
const FontStyle = Quill.import('attributors/style/font');
const AlignStyle = Quill.import('attributors/style/align');
const DirectionStyle = Quill.import('attributors/style/direction');
Quill.register(BackgroundStyle, true);
Quill.register(ColorStyle, true);
Quill.register(SizeStyle, true);
Quill.register(FontStyle, true);
Quill.register(AlignStyle, true);
Quill.register(DirectionStyle, true);

frappe.ui.form.ControlTextEditor = frappe.ui.form.ControlCode.extend({
	make_wrapper() {
		this._super();
		this.$wrapper.find(".like-disabled-input").addClass("ql-editor");
	},

	make_input() {
		this.has_input = true;
		this.Quill = Quill;
		this.make_quill_editor();
	},

	make_quill_editor() {
		if (this.quill) return;
		const show_template = this.df.options == "Template" ? true : false;
		this.quill_container = $(frappe.render_template("text_editor", {...this.get_tooltips(), showtemplate: show_template})).appendTo(this.input_area);
		this.quill = new Quill(this.quill_container[2], this.get_quill_options());

		this.make_template_editor()

		this.bind_events();
	},

	make_template_editor() {
		const me = this;
		if (["Email Template"].includes(this.doctype)) {
			const toolbar = this.quill.getModule('toolbar');
			toolbar.addHandler('template-blot', function() {
				if(!me.field_selector) {
					me.field_selector = new TemplateFieldSelector(me);
				} else {
					me.field_selector.make_dialog();
				}
			});
		}
	},

	bind_events() {
		this.quill.on('text-change', frappe.utils.debounce((delta, oldDelta, source) => {
			if (!this.is_quill_dirty(source)) return;

			const input_value = this.get_input_value();
			this.parse_validate_and_set_in_model(input_value);
		}, 300));

		$(this.quill.root).on('keydown', (e) => {
			const key = frappe.ui.keys.get_key(e);
			if (['ctrl+b', 'meta+b'].includes(key)) {
				e.stopPropagation();
			}
		});

		$(this.quill.root).on('drop', (e) => {
			e.stopPropagation();
		});

		// table commands
		this.$wrapper.on('click', '.ql-table .ql-picker-item', (e) => {
			const $target = $(e.currentTarget);
			const action = $target.data().value;
			e.preventDefault();

			const table = this.quill.getModule('table');
			if (action === 'insert-table') {
				table.insertTable(2, 2);
			} else if (action === 'insert-row-above') {
				table.insertRowAbove();
			} else if (action === 'insert-row-below') {
				table.insertRowBelow();
			} else if (action === 'insert-column-left') {
				table.insertColumnLeft();
			} else if (action === 'insert-column-right') {
				table.insertColumnRight();
			} else if (action === 'delete-row') {
				table.deleteRow();
			} else if (action === 'delete-column') {
				table.deleteColumn();
			} else if (action === 'delete-table') {
				table.deleteTable();
			}

			if (action !== 'delete-row') {
				table.balanceTables();
			}

			e.preventDefault();
		});
	},

	is_quill_dirty(source) {
		if (source === 'api') return false;
		let input_value = this.get_input_value();
		return this.value !== input_value;
	},

	get_quill_options() {
		return {
			modules: {
				toolbar: this.quill_container[0],
				table: true
			},
			theme: 'snow'
		};
	},

	get_tooltips() {
		return {
			"header": __("Text Size"),
			"bold": __("Bold"),
			"italic": __("Add italic text <cmd+i>"),
			"underline": __("Underline"),
			"blockquote": __("Quote"),
			"codeblock": __("Code"),
			"link": __("Link"),
			"image": __("Image"),
			"orderedlist": __("Ordered list"),
			"bulletlist": __("Bullet list"),
			"align": __("Align"),
			"indent": __("Indent"),
			"table": __("Add a table"),
			"clean": __("Remove formatting"),
			"templateblot": __("Add a variable")
		}
	},

	parse(value) {
		if (value == null) {
			value = "";
		}
		return frappe.dom.remove_script_and_style(value);
	},

	set_formatted_input(value) {
		if (!this.quill) return;
		if (value === this.get_input_value()) return;
		if (!value) {
			// clear contents for falsy values like '', undefined or null
			this.quill.setText('');
			return;
		}

		// set html without triggering a focus
		const delta = this.quill.clipboard.convert({ html: value, text: '' });
		this.quill.setContents(delta);
	},

	get_input_value() {
		let value = this.quill ? this.quill.root.innerHTML : '';
		// quill keeps ol as a common container for both type of lists
		// and uses css for appearances, this is not semantic
		// so we convert ol to ul if it is unordered
		const $value = $(`<div>${value}</div>`);
		$value.find('ol li[data-list=bullet]:first-child').each((i, li) => {
			let $li = $(li);
			let $parent = $li.parent();
			let $children = $parent.children();
			let $ul = $('<ul>').append($children);
			$parent.replaceWith($ul);
		});
		value = $value.html();
		return value;
	}
});