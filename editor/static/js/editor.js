document.addEventListener('DOMContentLoaded', () => {
	const novelText = document.getElementById('novel-text');
	const saveStatus = document.getElementById('save-status');
	const charCount = document.getElementById('char-count');
	const lastModified = document.getElementById('last-modified');
	const saveButton = document.getElementById('save-button');
	const fullscreenButton = document.getElementById('fullscreen-button');

	if (!novelText || !saveStatus || !charCount || !lastModified) {
		return;
	}

	let saveTimer = null;

	novelText.innerText = initialContent;
	updateCharCount();
	novelText.focus();

	function updateCharCount() {
		charCount.innerText = `文字数: ${novelText.innerText.length}`;
	}

	function saveText(showDialog = false) {
		const content = novelText.innerText;
		saveStatus.innerText = '保存中...';

		fetch('/save', {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json'
			},
			body: JSON.stringify({ path: filePath, content })
		})
			.then((response) => {
				if (!response.ok) {
					throw new Error('save failed');
				}
				return response.json();
			})
			.then((data) => {
				saveStatus.innerText = '自動保存済み';
				charCount.innerText = `文字数: ${data.length}`;
				lastModified.innerText = `最終保存: ${data.last_modified}`;
				if (showDialog) {
					alert(data.message);
				}
			})
			.catch(() => {
				saveStatus.innerText = '保存失敗';
			});
	}

	function queueSave() {
		updateCharCount();
		saveStatus.innerText = '変更あり';
		window.clearTimeout(saveTimer);
		saveTimer = window.setTimeout(() => saveText(false), 400);
	}

	novelText.addEventListener('input', queueSave);
	saveButton?.addEventListener('click', () => {
		window.clearTimeout(saveTimer);
		saveText(true);
	});
	fullscreenButton?.addEventListener('click', () => {
		if (!document.fullscreenElement) {
			document.documentElement.requestFullscreen?.();
			return;
		}
		document.exitFullscreen?.();
	});

	document.addEventListener('keydown', (event) => {
		if ((event.ctrlKey || event.metaKey) && event.key === 's') {
			event.preventDefault();
			window.clearTimeout(saveTimer);
			saveText(true);
		}
	});
});
