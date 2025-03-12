<template>
  <div class="queue-status-container">
    <div class="queue-status" :class="{ 'status-busy': isBusy, 'status-available': !isBusy }">
      <el-tooltip :content="tooltipContent" placement="top">
        <div class="status-indicator">
          <i :class="statusIcon"></i>
          <span>{{ statusText }}</span>
          <span v-if="showDetails">({{ activeRequests }}/{{ maxRequests }})</span>
        </div>
      </el-tooltip>
    </div>
  </div>
</template>

<script>
export default {
  name: 'QueueStatus',
  props: {
    checkInterval: {
      type: Number,
      default: 10000 // 默认10秒检查一次
    }
  },
  data() {
    return {
      activeRequests: 0,
      maxRequests: 4,
      isAvailable: true,
      lastUpdated: null,
      intervalId: null,
      loading: false,
      error: null,
      showDetails: false
    }
  },
  computed: {
    isBusy() {
      return this.activeRequests >= this.maxRequests;
    },
    statusIcon() {
      if (this.loading) return 'el-icon-loading';
      if (this.error) return 'el-icon-warning';
      return this.isBusy ? 'el-icon-time' : 'el-icon-success';
    },
    statusText() {
      if (this.loading) return '检查中...';
      if (this.error) return '状态未知';
      return this.isBusy ? '队列繁忙' : '队列空闲';
    },
    tooltipContent() {
      if (this.error) return `无法获取队列状态: ${this.error}`;
      if (this.loading) return '正在获取队列状态...';
      
      const timeAgo = this.lastUpdated ? this.getTimeAgo(this.lastUpdated) : '未知';
      return `当前活跃请求: ${this.activeRequests}/${this.maxRequests}，最后更新: ${timeAgo}`;
    }
  },
  methods: {
    async fetchQueueStatus() {
      this.loading = true;
      this.error = null;
      
      try {
        const response = await fetch('/api/queue-status');
        if (!response.ok) {
          throw new Error(`HTTP error ${response.status}`);
        }
        
        const data = await response.json();
        this.activeRequests = data.active_requests;
        this.maxRequests = data.max_requests;
        this.isAvailable = data.queue_available;
        this.lastUpdated = new Date();
      } catch (err) {
        console.error('获取队列状态失败:', err);
        this.error = err.message;
      } finally {
        this.loading = false;
      }
    },
    getTimeAgo(date) {
      const now = new Date();
      const seconds = Math.floor((now - date) / 1000);
      
      if (seconds < 60) return `${seconds}秒前`;
      if (seconds < 3600) return `${Math.floor(seconds / 60)}分钟前`;
      return `${Math.floor(seconds / 3600)}小时前`;
    },
    toggleDetails() {
      this.showDetails = !this.showDetails;
    }
  },
  mounted() {
    // 初始化时获取状态
    this.fetchQueueStatus();
    
    // 设置定时检查
    this.intervalId = setInterval(this.fetchQueueStatus, this.checkInterval);
    
    // 添加点击事件显示/隐藏详情
    this.$el.addEventListener('click', this.toggleDetails);
  },
  beforeUnmount() {
    // 清除定时器
    if (this.intervalId) {
      clearInterval(this.intervalId);
    }
    
    // 移除事件监听
    this.$el.removeEventListener('click', this.toggleDetails);
  }
}
</script>

<style scoped>
.queue-status-container {
  margin: 10px 0;
  display: flex;
  justify-content: flex-end;
}

.queue-status {
  padding: 5px 10px;
  border-radius: 4px;
  font-size: 0.9em;
  display: inline-flex;
  align-items: center;
  cursor: pointer;
  transition: all 0.3s;
}

.status-busy {
  background-color: #fef0f0;
  color: #f56c6c;
  border: 1px solid #fbc4c4;
}

.status-available {
  background-color: #f0f9eb;
  color: #67c23a;
  border: 1px solid #c2e7b0;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 5px;
}

.status-indicator i {
  font-size: 1.1em;
}
</style> 