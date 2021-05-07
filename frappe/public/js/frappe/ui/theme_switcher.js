frappe.provide('frappe.ui');

frappe.ui.ThemeSwitcher = class ThemeSwitcher {
	constructor() {
		this.setup_dialog();
		this.refresh();
	}

	setup_dialog() {
		this.dialog = new frappe.ui.Dialog({
			title: __("Switch Theme")
		});
		this.body = $(`<div class="theme-grid"></div>`).appendTo(this.dialog.$body);
		this.bind_events();
	}

	bind_events() {
		this.dialog.$wrapper.on('keydown', (e) => {
			if (!this.themes) return;

			const key = frappe.ui.keys.get_key(e);
			let increment_by;

			if (key === "right") {
				increment_by = 1;
			} else if (key === "left") {
				increment_by = -1;
			} else {
				return;
			}

			const current_index = this.themes.findIndex(theme => {
				return theme.name === this.current_theme;
			});

			const new_theme = this.themes[current_index + increment_by];
			if (!new_theme) return;

			new_theme.$html.click();
			return false;
		});
	}

	refresh() {
		this.current_theme = document.body.dataset.theme;
		this.fetch_themes().then(() => {
			this.render();
		});
	}

	fetch_themes() {
		return new Promise((resolve) => {
			this.themes = [
				{
					name: "light",
					label: __("Light"),
				},
				{
					name: "dark",
					label: __("Night"),
				}
			];

			resolve(this.themes);
		});
	}

	render() {
		this.themes.forEach((theme) => {
			let html = this.get_preview_html(theme);
			html.appendTo(this.body);
			theme.$html = html;
		});
	}


	get_preview_html(theme) {
		const preview = $(`<div class="${this.current_theme == theme.name ? "selected" : "" }">
			<div data-theme=${theme.name}>
				<div class="background">
					<div>
						<div class="preview-check">${frappe.utils.icon('tick', 'xs')}</div>
					</div>
					<div class="navbar"></div>
					<div class="p-2">
						<div class="toolbar">
							<span class="text"></span>
							<span class="primary"></span>
						</div>
						<div class="foreground"></div>
						<div class="foreground"></div>
					</div>
				</div>
			</div>
			<div class="mt-3 text-center">
				<h5 class="theme-title">${theme.label}</h5>
			</div>
		</div>`);

		// preview.on('mouseover', () => {
		// 	this.toggle_theme(theme.name, true)
		// })

		// preview.on('mouseleave', () => {
		// 	this.toggle_theme(this.current_theme, true)
		// })

		preview.on('click', () => {
			this.themes.forEach((th) => {
				th.$html.removeClass("selected");
			});

			preview.addClass("selected");
			this.toggle_theme(theme.name);
		});

		return preview;
	}

	toggle_theme(theme, preview=false) {
		if (!preview) {
			document.body.dataset.theme = theme.toLowerCase();
			frappe.show_alert("Theme Changed", 3);

			frappe.call('frappe.core.doctype.user.user.switch_theme', {
				theme: toTitle(theme)
			});
		} else {
			document.body.dataset.theme = theme.toLowerCase();
		}
	}

	show() {
		this.dialog.show();
	}

	hide() {
		this.dialog.hide();
	}
};