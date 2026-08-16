document.addEventListener('DOMContentLoaded', () => {
	const uploadRoot = document.querySelector('.illustration-upload');
	if (!uploadRoot) {
		return;
	}

	const pasteTarget = uploadRoot.querySelector('.paste-target');
	const preview = uploadRoot.querySelector('.illustration-preview');
	const previewImage = preview?.querySelector('img');
	const uploadButton = uploadRoot.querySelector('.illustration-upload-button');
	const cancelButton = uploadRoot.querySelector('.illustration-cancel-button');
	const errorMessage = uploadRoot.querySelector('.illustration-error');
	const statusMessage = uploadRoot.querySelector('.illustration-status');
	const nodePath = uploadRoot.dataset.nodePath;
	let selectedImage = null;
	let previewUrl = null;

	function showMessage(element, text) {
		if (!element) {
			return;
		}
		element.innerText = text;
		element.hidden = false;
	}

	function hideMessage(element) {
		if (!element) {
			return;
		}
		element.innerText = '';
		element.hidden = true;
	}

	function clearPreview() {
		selectedImage = null;
		if (previewUrl) {
			URL.revokeObjectURL(previewUrl);
			previewUrl = null;
		}
		if (previewImage) {
			previewImage.removeAttribute('src');
		}
		if (preview) {
			preview.hidden = true;
		}
		if (uploadButton) {
			uploadButton.disabled = true;
		}
		if (cancelButton) {
			cancelButton.disabled = true;
		}
	}

	function setPreview(file) {
		clearPreview();
		selectedImage = file;
		previewUrl = URL.createObjectURL(file);
		if (previewImage) {
			previewImage.src = previewUrl;
		}
		if (preview) {
			preview.hidden = false;
		}
		if (uploadButton) {
			uploadButton.disabled = false;
		}
		if (cancelButton) {
			cancelButton.disabled = false;
		}
		hideMessage(errorMessage);
		hideMessage(statusMessage);
	}

	function pastedImage(event) {
		const items = event.clipboardData?.items || [];
		for (const item of items) {
			if (item.type && item.type.startsWith('image/')) {
				return item.getAsFile();
			}
		}
		return null;
	}

	function convertToPng(file) {
		if (file.type === 'image/png') {
			return Promise.resolve(file);
		}

		return new Promise((resolve, reject) => {
			const image = new Image();
			const sourceUrl = URL.createObjectURL(file);
			image.onload = () => {
				const canvas = document.createElement('canvas');
				canvas.width = image.naturalWidth;
				canvas.height = image.naturalHeight;
				canvas.getContext('2d').drawImage(image, 0, 0);
				URL.revokeObjectURL(sourceUrl);
				canvas.toBlob((blob) => {
					if (!blob) {
						reject(new Error('conversion failed'));
						return;
					}
					resolve(new File([blob], 'illust.png', { type: 'image/png' }));
				}, 'image/png');
			};
			image.onerror = () => {
				URL.revokeObjectURL(sourceUrl);
				reject(new Error('image load failed'));
			};
			image.src = sourceUrl;
		});
	}

	pasteTarget?.addEventListener('paste', (event) => {
		const file = pastedImage(event);
		if (!file) {
			showMessage(errorMessage, '画像データを取得できませんでした。');
			return;
		}
		event.preventDefault();
		convertToPng(file)
			.then((pngFile) => setPreview(pngFile))
			.catch(() => showMessage(errorMessage, '画像データを取得できませんでした。'));
	});

	pasteTarget?.addEventListener('click', () => {
		pasteTarget.focus();
	});

	cancelButton?.addEventListener('click', () => {
		clearPreview();
		hideMessage(errorMessage);
		hideMessage(statusMessage);
	});

	uploadButton?.addEventListener('click', () => {
		if (!selectedImage) {
			return;
		}

		const formData = new FormData();
		formData.append('node_path', nodePath);
		formData.append('image', selectedImage, 'illust.png');
		uploadButton.disabled = true;
		hideMessage(errorMessage);
		hideMessage(statusMessage);

		fetch('/node/illustration', {
			method: 'POST',
			body: formData
		})
			.then((response) => {
				if (!response.ok) {
					return response.text().then((text) => {
						throw new Error(text || 'upload failed');
					});
				}
				return response.json();
			})
			.then(() => {
				showMessage(statusMessage, '保存しました。');
				window.location.reload();
			})
			.catch(() => {
				showMessage(errorMessage, '保存に失敗しました。');
				uploadButton.disabled = false;
			});
	});
});
