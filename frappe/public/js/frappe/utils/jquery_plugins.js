// add <option> list to <select>
(function($) {
	$.fn.add_options = function(options_list) {
		// create options
		for(var i=0, j=options_list.length; i<j; i++) {
			var v = options_list[i];
			var value = null;
			var label = null;
			if (!is_null(v)) {
				var is_value_null = is_null(v.value);
				var is_label_null = is_null(v.label);
				var is_disabled = Boolean(v.disabled);

				if (is_value_null && is_label_null) {
					value = v;
					label = __(v);
				} else {
					value = is_value_null ? "" : v.value;
					label = is_label_null ? __(value) : __(v.label);
				}
			}
			$('<option>').html(cstr(label))
				.attr('value', value)
				.prop('disabled', is_disabled)
				.appendTo(this);
		}
		// select the first option
		this.selectedIndex = 0;
		return $(this);
	};
	$.fn.set_working = function() {
		this.prop('disabled', true);
	};
	$.fn.done_working = function() {
		this.prop('disabled', false);
	};
})(jQuery);
