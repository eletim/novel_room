document.addEventListener('DOMContentLoaded', (event) => {
	const novelText = document.getElementById('novel-text');

	if (!novelText) {
		console.error('novel-text element not found');
		return;
	}

	// 初期コンテンツを設定
	novelText.innerText = initialContent;

	console.log('docId:', docId);
	console.log('Initial content:', novelText.innerText);

	// テキストを保存する関数
	function saveText(showDialog = false) {
		const content = novelText.innerText; // `innerText`に変更
		const length = content.length;
		console.log('Saving content:', content);

		fetch('/save', {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json'
			},
			body: JSON.stringify({ content, length, doc_id: docId })
		}).then(response => response.json())
			.then(data => {
				console.log('Save response:', data);
				if (showDialog) {
					alert(data.message);
				}
			}).catch(error => {
				console.error('Error saving content:', error);
			});
	}

	// テキストエリアの内容が変更されたときに自動保存
	novelText.addEventListener('input', () => {
		saveText();
	});

	// Ctrl + S キーが押されたときにテキストを保存
	document.addEventListener('keydown', (event) => {
		if (event.ctrlKey && event.key === 's') {
			event.preventDefault(); // ブラウザのデフォルトの保存ダイアログを防ぐ
			saveText(true);
		}
	});
});
