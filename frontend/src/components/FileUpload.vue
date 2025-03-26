const uploadFile = async (file) => {
  try {
    // 检查文件大小是否超过限制（100MB）
    if (file.size > 100 * 1024 * 1024) {
      // 如果超过限制，使用分片上传
      await uploadLargeFile(file);
    } else {
      // 小文件直接上传
      await uploadSmallFile(file);
    }
  } catch (error) {
    console.error('上传失败:', error);
    ElMessage.error('上传失败，请重试');
  }
};

// 小文件上传
const uploadSmallFile = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await axios.post('/api/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  });
  
  if (response.data.success) {
    ElMessage.success('上传成功');
    // 处理上传成功后的逻辑
  }
};

// 大文件分片上传
const uploadLargeFile = async (file) => {
  const CHUNK_SIZE = 10 * 1024 * 1024; // 10MB 分片大小
  const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
  let uploadedChunks = 0;
  
  // 初始化上传会话
  const initResponse = await axios.post('/api/upload/init', {
    filename: file.name,
    totalSize: file.size,
    totalChunks: totalChunks
  });
  
  const sessionId = initResponse.data.sessionId;
  
  for (let i = 0; i < totalChunks; i++) {
    const start = i * CHUNK_SIZE;
    const end = Math.min(start + CHUNK_SIZE, file.size);
    const chunk = file.slice(start, end);
    
    const formData = new FormData();
    formData.append('file', chunk);
    formData.append('sessionId', sessionId);
    formData.append('chunkIndex', i);
    formData.append('totalChunks', totalChunks);
    
    await axios.post('/api/upload/chunk', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    
    uploadedChunks++;
    // 更新上传进度
    const progress = Math.round((uploadedChunks / totalChunks) * 100);
    ElMessage.info(`上传进度: ${progress}%`);
  }
  
  // 完成上传
  const completeResponse = await axios.post('/api/upload/complete', {
    sessionId: sessionId
  });
  
  if (completeResponse.data.success) {
    ElMessage.success('上传成功');
    // 处理上传成功后的逻辑
  }
}; 