<template>
  <div class="container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>论文格式检查</h2>
          <QueueStatus />
        </div>
      </template>
      
      <!-- 上传表单区域 -->
      <div class="form-container">
        <el-form :model="form" label-width="120px">
          <el-form-item label="论文格式模板">
            <el-select 
              v-model="form.template" 
              placeholder="请选择论文格式模板"
              :disabled="isAnyFileProcessing"
            >
              <el-option label="阳光学院论文格式" value="sunshine" />
              <el-option label="厦门大学论文格式" value="xmu" />
            </el-select>
          </el-form-item>
          <el-form-item label="论文文件">
            <el-upload
              ref="upload"
              class="upload-demo"
              :http-request="customUpload"
              :data="form"
              :on-success="handleSuccess"
              :on-error="handleError"
              :before-upload="beforeUpload"
              :on-remove="handleRemove"
              :on-change="handleChange"
              :auto-upload="false"
              accept=".docx"
              :disabled="isAnyFileProcessing || documentList.length >= 5"
              :limit="5"
              :on-exceed="handleExceed"
              :file-list="fileList"
            >
              <template #trigger>
                <el-button type="primary" :disabled="isAnyFileProcessing || documentList.length >= 5">
                  选择文件 ({{ currentFileCount }}/5)
                </el-button>
              </template>
              <el-button
                class="ml-3"
                type="success"
                @click="submitUpload"
                :disabled="fileList.length === 0 || !form.template || isAnyFileProcessing"
              >
                {{ isAnyFileProcessing ? '处理中...' : '开始检查' }}
              </el-button>
            </el-upload>
          </el-form-item>
        </el-form>  
      </div>
      
      <!-- 结果显示区域 -->
      <div class="result-container">
        <div v-if="documentList.length > 0">
          <el-tabs v-model="activeTabName" type="card" class="document-tabs" closable @tab-remove="removeDocument">
            <el-tab-pane 
              v-for="doc in documentList" 
              :key="doc.id" 
              :label="doc.filename" 
              :name="doc.id"
            >
              <div class="tab-content">
                <div class="document-info">
                  <div class="info-item">
                    <span class="label">文件名:</span>
                    <span class="value">{{ doc.filename }}</span>
                  </div>
                  <div class="info-item">
                    <span class="label">模板:</span>
                    <span class="value">{{ doc.template === 'sunshine' ? '阳光学院论文格式' : '厦门大学论文格式' }}</span>
                  </div>
                  <div class="info-item">
                    <span class="label">状态:</span>
                    <span class="value status" :class="getStatusClass(doc)">{{ getStatusText(doc) }}</span>
                  </div>
                </div>
                
                <div v-if="doc.isProcessing" class="processing-status">
                  <el-progress
                    v-if="doc.uploadProgress > 0 && doc.uploadProgress < 100"
                    :percentage="doc.uploadProgress"
                    :format="progressFormat"
                  />
                  <div v-else class="loading-spinner">
                    <el-icon class="is-loading"><Loading /></el-icon>
                    <span>正在分析...</span>
                  </div>
                </div>
                
                <div v-else-if="doc.result" v-html="renderResult(doc.result)" class="result-content"></div>
                <div v-else-if="doc.errorInfo" class="error-result">
                  <h4>发生错误：</h4>
                  <p class="error-message">{{ doc.errorInfo.error }}</p>
                  <p v-if="doc.errorInfo.detail" class="error-detail">{{ doc.errorInfo.detail }}</p>
                  <div v-if="doc.errorInfo.code === 401" class="error-solution">
                    <p>可能的解决方案：</p>
                    <ul>
                      <li>检查 API 密钥是否正确</li>
                      <li>确认 API 密钥未过期</li>
                      <li>联系管理员重新配置 API 密钥</li>
                    </ul>
                  </div>
                </div>
                <div v-else class="empty-result">
                  <p>点击"开始检查"按钮开始分析论文格式</p>
                </div>
                
                <div class="action-buttons" v-if="!doc.isProcessing">
                  <el-button 
                    type="primary" 
                    size="small" 
                    @click="reanalyzeDocument(doc.id)"
                    :disabled="isAnyFileProcessing"
                  >
                    重新分析
                  </el-button>
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>
        <div v-else class="empty-documents">
          <p>请选择论文格式模板并上传文件进行检查</p>
        </div>
      </div>
    </el-card>
    
    <!-- 全局加载状态 -->
    <el-loading 
      v-model:full-screen="fullscreenLoading" 
      element-loading-text="正在分析论文格式，请稍候..."
      :lock="true"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { ElMessage, ElLoading, ElMessageBox } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import axios from 'axios'
import MarkdownIt from 'markdown-it'
import JSZip from 'jszip'
import QueueStatus from './components/QueueStatus.vue'
import { v4 as uuidv4 } from 'uuid'

const md = new MarkdownIt()

const form = reactive({
  template: '',
})

// 文件上传相关
const upload = ref(null)
const fileList = ref([])
const fullscreenLoading = ref(false)

// 文档管理
const documentList = ref([])
const activeTabName = ref('')

// 计算属性
const isAnyFileProcessing = computed(() => {
  return documentList.value.some(doc => doc.isProcessing)
})

// 计算当前选择的文件数量
const currentFileCount = computed(() => {
  return fileList.value.length
})

// 计算当前已处理或正在处理的文档数量
const currentDocumentCount = computed(() => {
  return documentList.value.length
})

// 文件进度显示
const progressFormat = (percentage) => {
  return percentage === 100 ? '处理中...' : `上传中 ${percentage}%`
}

// 处理超出文件数量限制
const handleExceed = (files) => {
  ElMessage.warning(`最多只能上传5份论文文件，已选择${fileList.value.length}个，本次选择${files.length}个，超出限制`)
}

// 检查文件是否已存在
const isFileExist = (file) => {
  const fileName = file.name
  // 同时检查fileList和documentList中是否存在同名文件
  return fileList.value.some(item => item.name === fileName) || 
         documentList.value.some(doc => doc.filename === fileName)
}

// 处理重复文件名，自动添加序号
const handleDuplicateFileName = (fileName) => {
  const lastDotIndex = fileName.lastIndexOf('.')
  const baseName = lastDotIndex !== -1 ? fileName.substring(0, lastDotIndex) : fileName
  const extension = lastDotIndex !== -1 ? fileName.substring(lastDotIndex) : ''
  
  let counter = 1
  let newFileName = `${baseName}_${counter}${extension}`
  
  // 检查新文件名是否仍然存在，如果存在，增加计数器
  while (fileList.value.some(item => item.name === newFileName) || 
         documentList.value.some(doc => doc.filename === newFileName)) {
    counter++
    newFileName = `${baseName}_${counter}${extension}`
  }
  
  return newFileName
}

const beforeUpload = (file) => {
  // 检查文件类型
  const isDocx = file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  if (!isDocx) {
    ElMessage.error('只能上传 .docx 格式的文件！')
    return false
  }
  
  // 检查文件数量，考虑已存在同名文件的情况
  const availableSlots = 5 - documentList.value.filter(doc => doc.filename !== file.name).length
  if (availableSlots <= 0) {
    ElMessage.warning('最多只能上传5份论文文件')
    return false
  }
  
  // 检查文件是否已存在
  if (isFileExist(file)) {
    // 检查是否在处理中
    const existingDoc = documentList.value.find(doc => doc.filename === file.name)
    if (existingDoc && existingDoc.isProcessing) {
      ElMessage.warning(`文件 "${file.name}" 正在处理中，无法替换`)
      return false
    }
    
    // 显示自定义操作对话框
    const handleDuplicate = async () => {
      try {
        await ElMessageBox.confirm(
          `文件 "${file.name}" 已存在。您希望如何处理？`,
          '文件重复提示',
          {
            confirmButtonText: '替换已有文件',
            cancelButtonText: '重命名新文件',
            distinguishCancelAndClose: true,
            type: 'warning',
            showClose: true,
            closeOnClickModal: false,
            closeOnPressEscape: true
          }
        ).then(() => {
          // 用户选择替换，先删除旧文件
          const oldDocIndex = documentList.value.findIndex(doc => doc.filename === file.name)
          if (oldDocIndex !== -1) {
            // 如果文档正在处理中，不允许替换
            if (documentList.value[oldDocIndex].isProcessing) {
              ElMessage.warning('无法替换正在处理中的文档')
              return
            }
            // 移除旧文档
            const oldDocId = documentList.value[oldDocIndex].id
            removeDocument(oldDocId)
          }
          
          // 从fileList中移除同名文件
          const oldFileIndex = fileList.value.findIndex(item => item.name === file.name)
          if (oldFileIndex !== -1) {
            fileList.value.splice(oldFileIndex, 1)
          }
          
          // 添加新文件到上传列表
          fileList.value.push(file)
          ElMessage.success(`已替换文件 "${file.name}"`)
        }).catch(action => {
          if (action === 'cancel') {
            // 用户选择重命名
            const newFileName = handleDuplicateFileName(file.name)
            
            // 创建一个新的File对象，使用新的文件名
            const newFile = new File([file], newFileName, { type: file.type })
            
            // 添加到上传列表
            fileList.value.push(newFile)
            ElMessage.success(`文件已重命名为 "${newFileName}"`)
          } else {
            // 用户点击关闭或者按Esc，跳过
            ElMessage.info(`已跳过文件 "${file.name}"`)
          }
        })
      } catch (error) {
        console.error('Dialog error:', error)
      }
    }
    
    // 执行对话框
    handleDuplicate()
    return false
  }
  
  return true
}

const handleChange = (file, fileList) => {
  // 更新文件列表，并确保最多只保留5个文件
  if (fileList.length > 5) {
    // 如果超过5个文件，只保留前5个
    fileList.value = fileList.slice(0, 5)
    ElMessage.warning('已自动保留前5个文件')
  } else {
    fileList.value = fileList
  }
}

const handleRemove = (file, fileList) => {
  // 更新文件列表
  fileList.value = fileList
}

const submitUpload = () => {
  if (!form.template) {
    ElMessage.error('请选择论文格式模板！')
    return
  }
  
  if (fileList.value.length === 0) {
    ElMessage.error('请先选择文件！')
    return
  }
  
  // 计算可用槽位，考虑可能的文件覆盖
  const filenamesToProcess = fileList.value.map(file => file.name)
  const existingFilenames = documentList.value.map(doc => doc.filename)
  
  // 找出要新增的文件（不在documentList中的文件）
  const newFiles = fileList.value.filter(file => !existingFilenames.includes(file.name))
  
  // 找出要覆盖的文件（同时在fileList和documentList中的文件）
  const overwriteFiles = fileList.value.filter(file => existingFilenames.includes(file.name))
  
  // 检查要覆盖的文件中是否有正在处理的文件
  const processingOverwrite = overwriteFiles.some(file => {
    const doc = documentList.value.find(d => d.filename === file.name)
    return doc && doc.isProcessing
  })
  
  if (processingOverwrite) {
    ElMessage.warning('无法替换正在处理中的文档，请等待处理完成或移除这些文件后再试')
    return
  }
  
  // 计算处理后的总文档数
  const totalAfterProcess = documentList.value.length - overwriteFiles.length + fileList.value.length
  
  if (totalAfterProcess > 5) {
    ElMessage.warning(`最多只能同时处理5份论文文件，当前选择的文件会导致总数超过限制`)
    return
  }
  
  // 提交所有文件
  upload.value.submit()
}

const customUpload = async (options) => {
  const { file } = options
  try {
    // 检查当前文档列表数量，如果已经达到5个，则跳过
    if (documentList.value.length >= 5) {
      ElMessage.warning(`最多只能同时处理5份论文文件，"${file.name}"已跳过`)
      return
    }
    
    // 检查是否存在同名文件，如果存在则自动覆盖
    const existingDocIndex = documentList.value.findIndex(doc => doc.filename === file.name)
    if (existingDocIndex !== -1) {
      // 如果文档正在处理中，不覆盖
      if (documentList.value[existingDocIndex].isProcessing) {
        ElMessage.warning(`文件 "${file.name}" 正在处理中，无法覆盖`)
        return
      }
      
      // 移除同名文档
      const oldDocId = documentList.value[existingDocIndex].id
      // 从documentList中移除
      documentList.value.splice(existingDocIndex, 1)
      
      // 如果activeTabName是被移除的文档，重置它
      if (activeTabName.value === oldDocId) {
        // 如果还有其他文档，选择第一个
        if (documentList.value.length > 0) {
          activeTabName.value = documentList.value[0].id
        } else {
          activeTabName.value = ''
        }
      }
      
      ElMessage.success(`已覆盖已有文件 "${file.name}"`)
    }
    
    // 创建新的文档对象
    const docId = uuidv4()
    const newDoc = {
      id: docId,
      filename: file.name,
      template: form.template,
      file: file,
      isProcessing: true,
      uploadProgress: 0,
      result: '',
      errorInfo: null,
      createdAt: new Date()
    }
    
    // 添加到文档列表
    documentList.value.push(newDoc)
    activeTabName.value = docId
    
    // 开始处理文件
    await processDocument(newDoc)
    
  } catch (error) {
    ElMessage.error(error.message || '上传失败，请重试')
  }
}

const processDocument = async (document) => {
  try {
    const file = document.file
    
    // 检查文件大小
    if (file.size === 0) {
      throw new Error('文件内容为空，请检查文件是否有效')
    }

    // 创建新的JSZip实例
    const zip = new JSZip()
    
    // 读取文件内容并添加到zip中
    const fileContent = await new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = (e) => {
        const content = e.target.result
        if (!content || content.byteLength === 0) {
          reject(new Error('文件读取失败，获取到的内容为空'))
        }
        resolve(content)
      }
      reader.onerror = () => reject(new Error('文件读取失败'))
      reader.readAsArrayBuffer(file)
    })
    
    // 将文件内容添加到zip中
    zip.file(file.name, fileContent)
    
    // 生成zip blob
    const zipBlob = await zip.generateAsync({
      type: 'blob',
      compression: 'DEFLATE',
      compressionOptions: {
        level: 9
      }
    })
    
    // 检查生成的zip文件大小
    if (zipBlob.size === 0) {
      throw new Error('压缩后的文件大小为0，请检查文件内容')
    }
    
    // 创建FormData对象
    const formData = new FormData()
    formData.append('file', new File([zipBlob], 'document.zip', { type: 'application/zip' }))
    formData.append('template', document.template)

    try {
      const response = await axios.post('/api/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        onUploadProgress: (progressEvent) => {
          // 更新特定文档的上传进度
          const index = documentList.value.findIndex(doc => doc.id === document.id)
          if (index !== -1) {
            documentList.value[index].uploadProgress = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total
            )
          }
        }
      })
      
      // 处理成功
      const index = documentList.value.findIndex(doc => doc.id === document.id)
      if (index !== -1) {
        documentList.value[index].result = response.data.result
        documentList.value[index].errorInfo = null
        documentList.value[index].isProcessing = false
        documentList.value[index].uploadProgress = 0
      }
      
      ElMessage.success(`文件 "${document.filename}" 检查完成`)
      
    } catch (error) {
      handleDocumentError(document, error)
    }
  } catch (error) {
    handleDocumentError(document, error)
  }
}

const handleDocumentError = (document, error) => {
  const index = documentList.value.findIndex(doc => doc.id === document.id)
  if (index === -1) return
  
  documentList.value[index].isProcessing = false
  documentList.value[index].uploadProgress = 0
  
  // 设置错误信息
  if (error.response) {
    // 服务器返回了错误响应
    const { status, data } = error.response
    
    // 设置错误信息对象
    documentList.value[index].errorInfo = {
      error: data.error || `请求失败 (${status})`,
      code: data.code || status,
      detail: data.detail || '服务器返回了错误响应'
    }
    
    // 根据状态码显示不同的错误消息
    if (status === 401) {
      ElMessage.error({
        message: `文件 "${document.filename}": 认证失败：API密钥无效或已过期`,
        duration: 5000
      })
    } else if (status === 503 || status === 504) {
      ElMessage.error({
        message: `文件 "${document.filename}": 服务暂时不可用，请稍后重试`,
        duration: 5000
      })
    } else {
      ElMessage.error({
        message: `文件 "${document.filename}": ${data.error || '请求失败，请稍后重试'}`,
        duration: 5000
      })
    }
  } else if (error.request) {
    // 请求已发送但没有收到响应
    documentList.value[index].errorInfo = {
      error: '无法连接到服务器',
      code: 0,
      detail: '请求已发送，但未收到服务器响应，请检查网络连接'
    }
    ElMessage.error(`文件 "${document.filename}": 无法连接到服务器，请检查网络连接`)
  } else {
    // 请求设置时发生错误
    documentList.value[index].errorInfo = {
      error: error.message || '请求错误',
      code: 0,
      detail: '发送请求时出现错误'
    }
    ElMessage.error(`文件 "${document.filename}": ${error.message || '请求错误'}`)
  }
}

const handleSuccess = (response, uploadFile, uploadFiles) => {
  // 注意：这个函数已经不再使用，处理成功在processDocument中完成
}

const handleError = (error) => {
  // 注意：这个函数已经不再使用，处理错误在handleDocumentError中完成
}

// 移除文档（关闭标签）
const removeDocument = (tabName) => {
  const index = documentList.value.findIndex(doc => doc.id === tabName)
  if (index !== -1) {
    // 如果文档正在处理中，显示警告
    if (documentList.value[index].isProcessing) {
      ElMessage.warning('无法移除正在处理中的文档')
      return
    }
    
    // 移除文档
    documentList.value.splice(index, 1)
    
    // 更新文件列表
    fileList.value = fileList.value.filter(file => {
      return !documentList.value.some(doc => doc.filename === file.name)
    })
    
    // 如果还有其他文档，选择第一个
    if (documentList.value.length > 0) {
      activeTabName.value = documentList.value[0].id
    }
  }
}

// 重新分析文档
const reanalyzeDocument = (docId) => {
  const index = documentList.value.findIndex(doc => doc.id === docId)
  if (index !== -1) {
    const document = documentList.value[index]
    
    // 重置文档状态
    document.isProcessing = true
    document.uploadProgress = 0
    document.result = ''
    document.errorInfo = null
    
    // 重新处理文档
    processDocument(document)
  }
}

// 获取状态文本
const getStatusText = (document) => {
  if (document.isProcessing) return '处理中'
  if (document.errorInfo) return '检查失败'
  if (document.result) return '检查完成'
  return '等待检查'
}

// 获取状态类名
const getStatusClass = (document) => {
  if (document.isProcessing) return 'status-processing'
  if (document.errorInfo) return 'status-error'
  if (document.result) return 'status-success'
  return 'status-waiting'
}

// 渲染结果
const renderResult = (text) => {
  // 去除多余空行
  const cleanText = text.replace(/\n\s*\n/g, '\n')
  // 使用markdown-it渲染文本
  return md.render(cleanText)
}
</script>

<style scoped>
.container {
  max-width: 1200px;
  margin: 20px auto;
  padding: 0 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.form-container {
  margin: 20px 0;
}

.result-container {
  margin-top: 20px;
  padding: 20px;
  background-color: #f5f7fa;
  border-radius: 4px;
  border: 1px solid #e4e7ed;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.12);
}

.document-tabs {
  margin-bottom: 20px;
}

.document-tabs :deep(.el-tabs__header) {
  margin-bottom: 15px;
}

.document-info {
  display: flex;
  flex-wrap: wrap;
  background-color: #fff;
  padding: 12px;
  border-radius: 4px;
  margin-bottom: 15px;
  border: 1px solid #e4e7ed;
}

.info-item {
  margin-right: 20px;
  display: flex;
  align-items: center;
}

.info-item .label {
  font-weight: bold;
  color: #606266;
  margin-right: 5px;
}

.info-item .value {
  color: #333;
}

.info-item .status {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
}

.status-processing {
  background-color: #e6f1fc;
  color: #409eff;
}

.status-error {
  background-color: #fef0f0;
  color: #f56c6c;
}

.status-success {
  background-color: #f0f9eb;
  color: #67c23a;
}

.status-waiting {
  background-color: #f4f4f5;
  color: #909399;
}

.processing-status {
  margin: 20px 0;
}

.loading-spinner {
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 20px 0;
  color: #409eff;
}

.loading-spinner i {
  margin-right: 8px;
  font-size: 18px;
}

.tab-content {
  padding: 10px;
}

.result-content {
  white-space: normal;
  line-height: 1.6;
  font-size: 14px;
  color: #333;
  padding: 15px;
  background-color: #fff;
  border-radius: 4px;
  max-height: 500px;
  overflow-y: auto;
  margin-top: 10px;
  border: 1px solid #e4e7ed;
}

.result-content :deep(p) {
  margin: 0.5em 0;
}

.result-content :deep(ul), .result-content :deep(ol) {
  margin: 0.5em 0;
  padding-left: 1.5em;
}

.error-result {
  padding: 15px;
  background-color: #fff;
  border-radius: 4px;
  border-left: 4px solid #f56c6c;
  margin-top: 10px;
}

.error-message {
  color: #f56c6c;
  font-weight: bold;
  margin-bottom: 10px;
}

.error-detail {
  color: #606266;
  margin-bottom: 15px;
}

.error-solution {
  background-color: #fef0f0;
  padding: 10px 15px;
  border-radius: 4px;
  margin-top: 10px;
}

.error-solution p {
  font-weight: bold;
  margin-bottom: 5px;
}

.error-solution ul {
  padding-left: 20px;
  margin: 5px 0;
}

.action-buttons {
  margin-top: 15px;
  display: flex;
  justify-content: flex-end;
}

.ml-3 {
  margin-left: 12px;
}

.empty-result, .empty-documents {
  text-align: center;
  color: #909399;
  padding: 20px;
  background-color: #fff;
  border-radius: 4px;
}
</style> 