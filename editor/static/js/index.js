function confirmDelete(event) {
	if (!confirm('本当に削除しますか？')) {
		event.preventDefault();
	}
}

function confirmDeleteFolder(event, folderId) {
	// フォルダ内のアイテムをチェックするためにサーバーサイドのチェックを呼び出します
	event.preventDefault();
	fetch(`/check_folder_empty/${folderId}`)
		.then(response => response.json())
		.then(data => {
			if (data.isEmpty) {
				if (confirm('本当に削除しますか？')) {
					event.target.submit();
				}
			} else {
				alert('フォルダ内にアイテムが存在するため、削除できません。');
			}
		});
}

function toggleOptions(docId) {
	var optionsDiv = document.getElementById('options-' + docId);
	if (optionsDiv.style.display === 'none' || optionsDiv.style.display === '') {
		optionsDiv.style.display = 'block';
	} else {
		optionsDiv.style.display = 'none';
	}
}
