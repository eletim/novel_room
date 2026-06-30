document.addEventListener('DOMContentLoaded', () => {
	document.querySelectorAll('.delete-form').forEach((form) => {
		form.addEventListener('submit', (event) => {
			if (!window.confirm('本当に削除しますか？')) {
				event.preventDefault();
			}
		});
	});
});
