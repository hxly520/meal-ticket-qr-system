import ElementPlus, { ElMessage, ElMessageBox } from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { computed, createApp, reactive } from 'vue/dist/vue.esm-bundler.js'
import {
  BadgeCheck,
  CalendarDays,
  ClipboardList,
  Download,
  FilePlus2,
  LogOut,
  Menu,
  Plus,
  QrCode,
  RefreshCw,
  Save,
  Search,
  Settings,
  ShieldCheck,
  Users,
  Utensils,
  X,
} from 'lucide-vue-next'
import axios from 'axios'
import './style.css'

const api = axios.create({ baseURL: '/api' })

const state = reactive({
  token: localStorage.getItem('token') || '',
  me: null,
  activeView: 'tickets',
  login: { username: 'admin', password: 'admin123456' },
  tickets: [],
  selectedTicketIds: [],
  users: [],
  userMode: 'list',
  settings: [],
  settingsForm: {},
  filters: { status: '', keyword: '' },
  pagination: { page: 1, page_size: 20, total: 0 },
  form: {
    employee_name: '',
    employee_userid: '',
    department: '',
    meal_date: new Date().toISOString().slice(0, 10),
    meal_types: ['lunch'],
    diner_count: 1,
  },
  userForm: {
    username: '',
    password: '',
    name: '',
    wecom_userid: '',
    department: '',
    roles: ['verifier'],
  },
  publicToken: location.pathname.startsWith('/ticket')
    ? new URLSearchParams(location.search).get('token') || ''
    : '',
  generatedUrl: '',
  generatedToken: '',
  generatedRows: [],
  verifyToken: new URLSearchParams(location.search).get('token') || '',
  verifyPreview: null,
  verifyResult: {
    type: '',
    title: '',
    message: '',
  },
  loginError: '',
  mobileNavOpen: false,
  loading: false,
  saving: false,
})

let scanLocked = false

api.interceptors.request.use((config) => {
  if (state.token) config.headers.Authorization = `Bearer ${state.token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.detail || '请求处理失败'
    if (error.response?.status === 401) {
      state.token = ''
      state.me = null
      localStorage.removeItem('token')
    }
    ElMessage.error(message)
    return Promise.reject(error)
  }
)

function hasRole(...roles) {
  return Boolean(state.me?.roles?.some((role) => roles.includes(role)))
}

function formatMeal(type) {
  return { breakfast: '早餐', lunch: '午餐', dinner: '晚餐' }[type] || type
}

function formatStatus(status) {
  return { unused: '未使用', used: '已核销', expired: '已过期', void: '已作废' }[status] || status
}

function formatDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
    .format(date)
    .replace(/\//g, '-')
}

function statusTag(status) {
  return { unused: 'warning', used: 'success', expired: 'info', void: 'danger' }[status] || 'info'
}

function sourceLabel(source) {
  return { manual: '手工', batch: '批量', wecom: '企微审批', wecom_approval: '企微审批' }[source] || source
}

function formatRoles(roles) {
  const labels = { admin: '管理员', hr: '行政制票', verifier: '饭堂核销', auditor: '行政查看' }
  return (roles || []).map((role) => labels[role] || role).join(' / ')
}

function setDefaultView() {
  if (hasRole('admin', 'hr', 'auditor')) {
    state.activeView = 'tickets'
    return
  }
  if (hasRole('verifier')) state.activeView = 'verify'
}

const navItems = computed(() =>
  [
    hasRole('admin', 'hr', 'auditor') && {
      key: 'tickets',
      label: '饭票管理',
      icon: QrCode,
      subtitle: '查询、作废、导出',
    },
    hasRole('admin', 'hr') && {
      key: 'create',
      label: '饭票生成',
      icon: FilePlus2,
      subtitle: '单张饭票',
    },
    hasRole('verifier') && {
      key: 'verify',
      label: '扫码核销',
      icon: BadgeCheck,
      subtitle: '饭堂核销',
    },
    hasRole('admin') && {
      key: 'settings',
      label: '系统设置',
      icon: Settings,
      subtitle: '企业微信参数',
    },
    hasRole('admin') && {
      key: 'users',
      label: '权限管理',
      icon: Users,
      subtitle: '账号与角色',
    },
  ].filter(Boolean)
)

const activeTitle = computed(
  () => navItems.value.find((item) => item.key === state.activeView)?.label || '后台管理'
)

const canManageTickets = computed(() => hasRole('admin', 'hr'))

const roleDefinitions = [
  { code: 'admin', label: '管理员', scope: '系统设置、账号权限、饭票全流程' },
  { code: 'hr', label: '行政制票', scope: '生成饭票、作废饭票、查看和导出记录' },
  { code: 'verifier', label: '饭堂核销', scope: '扫码打开饭票后执行核销' },
  { code: 'auditor', label: '行政查看', scope: '查看饭票记录和导出报表' },
]

const ticketStats = computed(() => {
  const stats = { unused: 0, used: 0, expired: 0, void: 0 }
  for (const item of state.tickets) {
    if (Object.prototype.hasOwnProperty.call(stats, item.status)) stats[item.status] += 1
  }
  return stats
})

async function login() {
  state.loginError = ''
  try {
    const res = await api.post('/auth/login', state.login)
    state.token = res.data.access_token
    localStorage.setItem('token', state.token)
    await loadMe()
    setDefaultView()
    await loadInitialData()
  } catch (error) {
    state.loginError = error.response?.data?.detail || '登录失败，请检查账号和密码'
  }
}

async function loadMe() {
  if (!state.token) return
  const res = await api.get('/auth/me')
  state.me = res.data
}

async function loadInitialData() {
  if (hasRole('admin', 'hr', 'auditor')) await loadTickets()
  if (hasRole('admin')) {
    await loadSettings()
    await loadUsers()
  }
  if (state.verifyToken && hasRole('admin', 'verifier')) {
    state.activeView = 'verify'
    await processScannedText(state.verifyToken)
  }
}

function logout() {
  state.token = ''
  state.me = null
  state.tickets = []
  state.pagination.total = 0
  localStorage.removeItem('token')
}

function switchView(key) {
  state.activeView = key
  state.mobileNavOpen = false
  if (key === 'tickets' && !state.tickets.length) loadTickets()
  if (key === 'settings' && !state.settings.length) loadSettings()
  if (key === 'users' && !state.users.length) loadUsers()
}

async function loadTickets() {
  if (!hasRole('admin', 'hr', 'auditor')) return
  state.loading = true
  try {
    const res = await api.get('/tickets', {
      params: {
        ...state.filters,
        page: state.pagination.page,
        page_size: state.pagination.page_size,
      },
    })
    state.tickets = res.data.items
    state.pagination.total = res.data.total
    state.pagination.page = res.data.page
    state.pagination.page_size = res.data.page_size
  } finally {
    state.loading = false
  }
}

async function searchTickets() {
  state.pagination.page = 1
  await loadTickets()
}

async function resetFilters() {
  state.filters.keyword = ''
  state.filters.status = ''
  await searchTickets()
}

async function changePage(page) {
  state.pagination.page = page
  await loadTickets()
}

async function changePageSize(size) {
  state.pagination.page_size = size
  state.pagination.page = 1
  await loadTickets()
}

async function loadSettings() {
  const res = await api.get('/settings')
  state.settings = res.data
  state.settingsForm = Object.fromEntries(res.data.map((item) => [item.key, item.value || '']))
}

async function saveSettings() {
  state.saving = true
  try {
    const res = await api.put('/settings', { values: state.settingsForm })
    state.settings = res.data
    state.settingsForm = Object.fromEntries(res.data.map((item) => [item.key, item.value || '']))
    ElMessage.success('系统设置已保存')
  } finally {
    state.saving = false
  }
}

async function createTicket() {
  const res = await api.post('/tickets/generate', state.form)
  state.generatedRows = res.data
  const first = res.data[0]
  state.generatedUrl = first?.qr_url || ''
  state.generatedToken = first?.qr_url ? new URL(first.qr_url).searchParams.get('token') || '' : ''
  ElMessage.success(`已生成 ${res.data.length} 张饭票`)
  await searchTickets()
}

async function loadUsers() {
  if (!hasRole('admin')) return
  const res = await api.get('/auth/users')
  state.users = res.data
}

async function createUser() {
  await api.post('/auth/users', state.userForm)
  ElMessage.success('账号已创建')
  state.userForm = {
    username: '',
    password: '',
    name: '',
    wecom_userid: '',
    department: '',
    roles: ['verifier'],
  }
  state.userMode = 'list'
  await loadUsers()
}

async function saveUser(row) {
  await api.put(`/auth/users/${row.id}`, {
    name: row.name,
    wecom_userid: row.wecom_userid || '',
    department: row.department || '',
    roles: row.roles,
    is_active: row.is_active,
  })
  ElMessage.success('账号权限已保存')
  await loadUsers()
}

async function voidTicket(row) {
  await ElMessageBox.confirm(`确认作废 ${row.employee_name} 的饭票？`, '作废确认', {
    confirmButtonText: '作废',
    cancelButtonText: '取消',
    type: 'warning',
  })
  await api.post(`/tickets/${row.id}/void`)
  ElMessage.success('饭票已作废')
  await loadTickets()
}

function handleTicketSelectionChange(rows) {
  state.selectedTicketIds = rows.map((row) => row.id)
}

async function voidSelectedTickets() {
  if (!state.selectedTicketIds.length) {
    ElMessage.warning('请选择需要作废的饭票')
    return
  }
  await ElMessageBox.confirm(
    `确认作废已选择的 ${state.selectedTicketIds.length} 张饭票？已核销饭票会自动跳过。`,
    '批量作废确认',
    {
      confirmButtonText: '批量作废',
      cancelButtonText: '取消',
      type: 'warning',
    },
  )
  const res = await api.post('/tickets/void-batch', { ids: state.selectedTicketIds })
  ElMessage.success(
    `已作废 ${res.data.updated} 张，跳过已核销 ${res.data.skipped_used} 张`,
  )
  state.selectedTicketIds = []
  await loadTickets()
}

async function previewTicket() {
  const token = state.verifyToken.trim()
  if (!token) {
    ElMessage.warning('请输入二维码 token')
    return
  }
  const res = await api.get('/tickets/verify/preview', { params: { token } })
  state.verifyPreview = res.data
}

function extractTokenFromScan(text) {
  const value = String(text || '').trim()
  if (!value) return ''
  try {
    const url = new URL(value)
    return url.searchParams.get('token') || value
  } catch {
    return value
  }
}

async function consumeTicket() {
  const token = state.verifyToken.trim()
  if (!token) {
    ElMessage.warning('请输入二维码 token')
    return
  }
  await api.post('/tickets/verify/consume', { token })
  ElMessage.success('饭票核销成功')
  await previewTicket()
  await loadTickets()
}

async function processScannedText(text) {
  if (scanLocked) return
  scanLocked = true
  const token = extractTokenFromScan(text)
  state.verifyToken = token
  state.verifyPreview = null
  state.verifyResult = {
    type: '',
    title: '正在核销',
    message: '已识别二维码，正在读取饭票信息',
  }
  try {
    await previewTicket()
    await api.post('/tickets/verify/consume', { token })
    await previewTicket()
    state.verifyResult = {
      type: 'success',
      title: '核销成功',
      message: '饭票状态已更新为已核销',
    }
    ElMessage.success('饭票核销成功')
  } catch (error) {
    try {
      await previewTicket()
    } catch {
      state.verifyPreview = null
    }
    state.verifyResult = {
      type: 'danger',
      title: '核销失败',
      message: error.response?.data?.detail || '二维码无法核销',
    }
  } finally {
    setTimeout(() => {
      scanLocked = false
    }, 1000)
  }
}

async function exportReport() {
  const res = await api.get('/reports/tickets.xlsx', { responseType: 'blob' })
  const url = URL.createObjectURL(res.data)
  const link = document.createElement('a')
  link.href = url
  link.download = 'meal-tickets.xlsx'
  link.click()
  URL.revokeObjectURL(url)
}

if (!state.publicToken) {
  if (state.token) {
    loadMe()
      .then(async () => {
        setDefaultView()
        await loadInitialData()
      })
      .catch(() => logout())
  }
}

const App = {
  components: {
    BadgeCheck,
    CalendarDays,
    ClipboardList,
    Download,
    FilePlus2,
    LogOut,
    Menu,
    Plus,
    QrCode,
    RefreshCw,
    Save,
    Search,
    Settings,
    ShieldCheck,
    Users,
    Utensils,
    X,
  },
  setup() {
    return {
      state,
      navItems,
      activeTitle,
      ticketStats,
      canManageTickets,
      roleDefinitions,
      login,
      logout,
      switchView,
      loadTickets,
      searchTickets,
      resetFilters,
      changePage,
      changePageSize,
      loadSettings,
      saveSettings,
      loadUsers,
      createUser,
      saveUser,
      createTicket,
      voidTicket,
      handleTicketSelectionChange,
      voidSelectedTickets,
      previewTicket,
      consumeTicket,
      exportReport,
      formatMeal,
      formatStatus,
      formatDateTime,
      statusTag,
      sourceLabel,
      formatRoles,
    }
  },
  template: `
    <main v-if="state.publicToken" class="ticket-page">
      <section class="ticket-panel">
        <div class="brand-line centered">
          <Utensils :size="28" />
          <h1>饭票二维码</h1>
        </div>
        <img
          class="public-qr"
          :src="'/api/tickets/qr?token=' + encodeURIComponent(state.publicToken)"
          alt="饭票二维码"
        />
      </section>
    </main>

    <main v-else-if="!state.token" class="login-page">
      <section class="login-panel">
        <div class="brand-line">
          <Utensils :size="28" />
          <h1>饭票二维码核销系统</h1>
        </div>
        <el-form label-position="top" @submit.prevent>
          <el-form-item label="账号">
            <el-input v-model="state.login.username" autocomplete="username" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="state.login.password" type="password" autocomplete="current-password" show-password />
          </el-form-item>
          <div v-if="state.loginError" class="login-error">{{ state.loginError }}</div>
          <el-button type="primary" class="full" @click="login">
            <ShieldCheck :size="16" /> 登录
          </el-button>
        </el-form>
      </section>
    </main>

    <main v-else class="app-shell">
      <div
        v-if="state.mobileNavOpen"
        class="mobile-backdrop"
        @click="state.mobileNavOpen = false"
      ></div>
      <aside class="sidebar" :class="{ open: state.mobileNavOpen }">
        <div class="brand-line compact">
          <Utensils :size="24" />
          <strong>饭票核销</strong>
          <button class="sidebar-close" type="button" @click="state.mobileNavOpen = false">
            <X :size="18" />
          </button>
        </div>
        <nav>
          <button
            v-for="item in navItems"
            :key="item.key"
            type="button"
            :class="{ active: state.activeView === item.key }"
            @click="switchView(item.key)"
          >
            <component :is="item.icon" :size="18" />
            <span>
              <strong>{{ item.label }}</strong>
              <small>{{ item.subtitle }}</small>
            </span>
          </button>
        </nav>
      </aside>

      <section class="workspace">
        <header class="topbar">
          <el-button class="mobile-menu-button" circle @click="state.mobileNavOpen = true">
            <Menu :size="18" />
          </el-button>
          <div>
            <h1>{{ activeTitle }}</h1>
            <p>{{ state.me?.name }} · {{ formatRoles(state.me?.roles) }}</p>
          </div>
          <el-button @click="logout"><LogOut :size="16" /> 退出</el-button>
        </header>

        <section v-if="state.activeView === 'tickets'" class="content-area">
          <div class="metric-row">
            <section class="metric-card">
              <span>当前页未使用</span>
              <strong>{{ ticketStats.unused }}</strong>
            </section>
            <section class="metric-card">
              <span>当前页已核销</span>
              <strong>{{ ticketStats.used }}</strong>
            </section>
            <section class="metric-card">
              <span>筛选总数</span>
              <strong>{{ state.pagination.total }}</strong>
            </section>
            <section class="metric-card">
              <span>每页记录</span>
              <strong>{{ state.pagination.page_size }}</strong>
            </section>
          </div>

          <section class="panel">
            <div class="panel-head">
              <div>
                <h2>饭票记录</h2>
                <p>行政核实与饭票状态追踪</p>
              </div>
              <div class="head-actions">
                <el-button @click="loadTickets"><RefreshCw :size="16" /> 刷新</el-button>
                <el-button
                  v-if="canManageTickets"
                  type="danger"
                  plain
                  :disabled="!state.selectedTicketIds.length"
                  @click="voidSelectedTickets"
                >
                  <BadgeCheck :size="16" /> 批量作废
                </el-button>
                <el-button type="success" @click="exportReport">
                  <Download :size="16" /> 导出
                </el-button>
              </div>
            </div>

            <div class="filters">
              <el-input
                v-model="state.filters.keyword"
                placeholder="姓名 / UserID / 部门 / 编号 / 审批单"
                clearable
                @keyup.enter="searchTickets"
              />
              <el-select v-model="state.filters.status" placeholder="状态" clearable>
                <el-option label="未使用" value="unused" />
                <el-option label="已核销" value="used" />
                <el-option label="已过期" value="expired" />
                <el-option label="已作废" value="void" />
              </el-select>
              <el-button type="primary" @click="searchTickets"><Search :size="16" /> 查询</el-button>
              <el-button @click="resetFilters">重置</el-button>
            </div>

            <el-table
              :data="state.tickets"
              height="520"
              v-loading="state.loading"
              stripe
              @selection-change="handleTicketSelectionChange"
            >
              <el-table-column v-if="canManageTickets" type="selection" width="46" fixed="left" />
              <el-table-column prop="ticket_no" label="饭票编号" min-width="170" show-overflow-tooltip />
              <el-table-column prop="approval_sp_no" label="审批单号" min-width="160" show-overflow-tooltip />
              <el-table-column prop="employee_name" label="员工" width="110" />
              <el-table-column prop="department" label="部门" width="130" show-overflow-tooltip />
              <el-table-column label="餐别" width="90">
                <template #default="{ row }">{{ formatMeal(row.meal_type) }}</template>
              </el-table-column>
              <el-table-column label="用餐人" width="100">
                <template #default="{ row }">{{ row.diner_index }} / {{ row.diner_count }}</template>
              </el-table-column>
              <el-table-column prop="meal_date" label="用餐日期" width="120" />
              <el-table-column label="来源" width="100">
                <template #default="{ row }">{{ sourceLabel(row.source) }}</template>
              </el-table-column>
              <el-table-column label="状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="statusTag(row.status)">{{ formatStatus(row.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="核销时间" width="190" show-overflow-tooltip>
                <template #default="{ row }">{{ formatDateTime(row.used_at) }}</template>
              </el-table-column>
              <el-table-column v-if="canManageTickets" label="操作" width="100" fixed="right">
                <template #default="{ row }">
                  <el-button
                    size="small"
                    type="danger"
                    plain
                    :disabled="row.status === 'used' || row.status === 'void'"
                    @click="voidTicket(row)"
                  >
                    作废
                  </el-button>
                </template>
              </el-table-column>
            </el-table>

            <div class="pagination-bar">
              <el-pagination
                v-model:current-page="state.pagination.page"
                v-model:page-size="state.pagination.page_size"
                :total="state.pagination.total"
                :page-sizes="[10, 20, 50, 100]"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="changePage"
                @size-change="changePageSize"
              />
            </div>
          </section>
        </section>

        <section v-if="state.activeView === 'create'" class="content-area">
          <section class="panel narrow-panel">
            <div class="panel-head">
              <div>
                <h2>生成饭票</h2>
                <p>按用餐人数和餐别批量创建饭票</p>
              </div>
            </div>

            <el-form class="create-form" label-position="top" @submit.prevent>
              <div class="form-grid">
                <el-form-item label="员工姓名">
                  <el-input v-model="state.form.employee_name" />
                </el-form-item>
                <el-form-item label="企业微信 UserID">
                  <el-input v-model="state.form.employee_userid" />
                </el-form-item>
                <el-form-item label="部门">
                  <el-input v-model="state.form.department" />
                </el-form-item>
                <el-form-item label="用餐日期">
                  <el-date-picker v-model="state.form.meal_date" value-format="YYYY-MM-DD" type="date" />
                </el-form-item>
                <el-form-item label="用餐人数">
                  <el-input-number v-model="state.form.diner_count" :min="1" :max="200" />
                </el-form-item>
                <el-form-item label="餐别">
                  <el-checkbox-group v-model="state.form.meal_types">
                    <el-checkbox-button label="breakfast">早餐</el-checkbox-button>
                    <el-checkbox-button label="lunch">午餐</el-checkbox-button>
                    <el-checkbox-button label="dinner">晚餐</el-checkbox-button>
                  </el-checkbox-group>
                </el-form-item>
                <el-form-item label="预计生成">
                  <el-input
                    :model-value="String((state.form.diner_count || 0) * state.form.meal_types.length) + ' 张饭票'"
                    readonly
                  />
                </el-form-item>
              </div>
              <div class="form-actions">
                <el-button type="primary" @click="createTicket"><Plus :size="16" /> 生成饭票</el-button>
              </div>
            </el-form>

            <section v-if="state.generatedRows.length" class="result-panel">
              <div>
                <h3>最新生成 {{ state.generatedRows.length }} 张饭票</h3>
                <p>{{ state.generatedRows[0]?.employee_name }} · {{ state.generatedRows[0]?.meal_date }}</p>
              </div>
              <img
                v-if="state.generatedToken"
                class="qr-preview"
                :src="'/api/tickets/qr?token=' + encodeURIComponent(state.generatedToken)"
                alt="饭票二维码"
              />
            </section>
          </section>
        </section>

        <section v-if="state.activeView === 'verify'" class="content-area verify-content">
          <section class="panel verify-panel">
            <div class="panel-head verify-head">
              <div>
                <h2>扫码核销</h2>
                <p>扫码打开饭票后自动核销</p>
              </div>
            </div>

            <section
              v-if="state.verifyResult.title"
              class="verify-result"
              :class="state.verifyResult.type"
            >
              <strong>{{ state.verifyResult.title }}</strong>
              <span>{{ state.verifyResult.message }}</span>
            </section>

            <section v-if="state.verifyPreview" class="verify-summary">
              <div>
                <span>饭票状态</span>
                <strong :class="'status-' + state.verifyPreview.status">{{ formatStatus(state.verifyPreview.status) }}</strong>
              </div>
              <div>
                <span>申请人</span>
                <strong>{{ state.verifyPreview.employee_name }}</strong>
              </div>
              <div>
                <span>部门</span>
                <strong>{{ state.verifyPreview.department || '-' }}</strong>
              </div>
              <div>
                <span>用餐时间</span>
                <strong>{{ state.verifyPreview.meal_date }} · {{ formatMeal(state.verifyPreview.meal_type) }}</strong>
              </div>
              <div>
                <span>用餐人</span>
                <strong>第 {{ state.verifyPreview.diner_index }} 人 / 共 {{ state.verifyPreview.diner_count }} 人</strong>
              </div>
              <div>
                <span>饭票编号</span>
                <strong>{{ state.verifyPreview.ticket_no }}</strong>
              </div>
            </section>

            <section v-if="!state.verifyResult.title && !state.verifyPreview" class="verify-empty">
              <BadgeCheck :size="34" />
              <strong>等待扫码</strong>
              <span>请使用手机相机或微信扫一扫饭票二维码</span>
            </section>
          </section>
        </section>

        <section v-if="state.activeView === 'settings'" class="content-area">
          <section class="panel">
            <div class="panel-head">
              <div>
                <h2>系统设置</h2>
                <p>企业微信审批、二维码域名与字段映射</p>
              </div>
              <el-button type="primary" :loading="state.saving" @click="saveSettings">
                <Settings :size="16" /> 保存设置
              </el-button>
            </div>

            <div class="settings-grid">
              <section class="settings-panel">
                <h3>基础设置</h3>
                <el-form label-position="top">
                  <el-form-item label="系统公网地址">
                    <el-input v-model="state.settingsForm.app_base_url" placeholder="https://meal.example.com" />
                  </el-form-item>
                  <el-form-item label="系统时区">
                    <el-input v-model="state.settingsForm.app_timezone" placeholder="Asia/Shanghai" />
                  </el-form-item>
                  <el-form-item label="票面公司名称">
                    <el-input v-model="state.settingsForm.ticket_company_name" placeholder="公司名称" />
                  </el-form-item>
                  <el-form-item label="票面版权声明">
                    <el-input
                      v-model="state.settingsForm.ticket_footer_text"
                      placeholder="版权归IT部所有，有问题联系欧阳祖宇"
                    />
                  </el-form-item>
                </el-form>
              </section>

              <section class="settings-panel">
                <h3>核销时间限制</h3>
                <el-form label-position="top">
                  <el-form-item label="早餐核销时间段">
                    <el-input v-model="state.settingsForm.meal_window_breakfast" placeholder="06:00-09:00" />
                  </el-form-item>
                  <el-form-item label="午餐核销时间段">
                    <el-input v-model="state.settingsForm.meal_window_lunch" placeholder="11:00-13:30" />
                  </el-form-item>
                  <el-form-item label="晚餐核销时间段">
                    <el-input v-model="state.settingsForm.meal_window_dinner" placeholder="17:00-19:30" />
                  </el-form-item>
                  <p class="field-hint">留空表示该餐别不限制核销时间，格式为 HH:MM-HH:MM。</p>
                </el-form>
              </section>

              <section class="settings-panel">
                <h3>企业微信应用</h3>
                <el-form label-position="top">
                  <el-form-item label="CorpID">
                    <el-input v-model="state.settingsForm.wecom_corp_id" />
                  </el-form-item>
                  <el-form-item label="AgentID">
                    <el-input v-model="state.settingsForm.wecom_agent_id" />
                  </el-form-item>
                  <el-form-item label="Secret">
                    <el-input v-model="state.settingsForm.wecom_secret" type="password" show-password />
                  </el-form-item>
                </el-form>
              </section>

              <section class="settings-panel">
                <h3>审批回调</h3>
                <el-form label-position="top">
                  <el-form-item label="Token">
                    <el-input v-model="state.settingsForm.wecom_approval_token" />
                  </el-form-item>
                  <el-form-item label="EncodingAESKey">
                    <el-input v-model="state.settingsForm.wecom_approval_aes_key" type="password" show-password />
                  </el-form-item>
                  <el-form-item label="审批模板 ID">
                    <el-input v-model="state.settingsForm.wecom_approval_template_id" />
                  </el-form-item>
                </el-form>
              </section>

              <section class="settings-panel">
                <h3>审批字段映射</h3>
                <el-form label-position="top">
                  <el-form-item label="用餐日期字段名">
                    <el-input v-model="state.settingsForm.wecom_field_meal_date" />
                  </el-form-item>
                  <el-form-item label="餐别字段名">
                    <el-input v-model="state.settingsForm.wecom_field_meal_type" />
                  </el-form-item>
                  <el-form-item label="用餐人数字段名">
                    <el-input v-model="state.settingsForm.wecom_field_diner_count" />
                  </el-form-item>
                  <el-form-item label="部门字段名">
                    <el-input v-model="state.settingsForm.wecom_field_department" />
                  </el-form-item>
                  <el-form-item label="部门ID映射">
                    <el-input
                      v-model="state.settingsForm.wecom_department_mapping"
                      type="textarea"
                      :rows="5"
                      placeholder="28=IT部&#10;35=行政部"
                    />
                  </el-form-item>
                  <el-form-item label="申请原因字段名">
                    <el-input v-model="state.settingsForm.wecom_field_reason" />
                  </el-form-item>
                </el-form>
              </section>
            </div>
          </section>
        </section>

        <section v-if="state.activeView === 'users'" class="content-area">
          <section class="panel">
            <div class="panel-head">
              <div>
                <h2>权限管理</h2>
                <p>账号、角色与企业微信 UserID</p>
              </div>
              <div class="head-actions">
                <el-button @click="state.userMode = 'create'"><Plus :size="16" /> 新增用户</el-button>
                <el-button @click="loadUsers"><RefreshCw :size="16" /> 刷新</el-button>
              </div>
            </div>

            <el-tabs v-model="state.userMode" class="user-tabs">
              <el-tab-pane label="用户列表" name="list">
                <el-table :data="state.users" class="user-table" stripe>
                  <el-table-column prop="username" label="账号" width="130" />
                  <el-table-column label="姓名" width="150">
                    <template #default="{ row }"><el-input v-model="row.name" /></template>
                  </el-table-column>
                  <el-table-column label="企业微信 UserID" min-width="180">
                    <template #default="{ row }"><el-input v-model="row.wecom_userid" placeholder="用于关联企微员工" /></template>
                  </el-table-column>
                  <el-table-column label="部门" min-width="150">
                    <template #default="{ row }"><el-input v-model="row.department" /></template>
                  </el-table-column>
                  <el-table-column label="角色" min-width="280">
                    <template #default="{ row }">
                      <el-select v-model="row.roles" multiple>
                        <el-option label="管理员" value="admin" />
                        <el-option label="行政制票" value="hr" />
                        <el-option label="饭堂核销" value="verifier" />
                        <el-option label="行政查看" value="auditor" />
                      </el-select>
                    </template>
                  </el-table-column>
                  <el-table-column label="启用" width="90">
                    <template #default="{ row }"><el-switch v-model="row.is_active" /></template>
                  </el-table-column>
                  <el-table-column label="操作" width="100" fixed="right">
                    <template #default="{ row }">
                      <el-button type="primary" plain size="small" @click="saveUser(row)">
                        <Save :size="14" /> 保存
                      </el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </el-tab-pane>

              <el-tab-pane label="新增用户" name="create">
                <div class="role-grid">
                  <section v-for="role in roleDefinitions" :key="role.code" class="role-card">
                    <strong>{{ role.label }}</strong>
                    <span>{{ role.scope }}</span>
                  </section>
                </div>

                <el-form class="create-form user-create-form" label-position="top" @submit.prevent>
                  <div class="form-grid">
                    <el-form-item label="账号">
                      <el-input v-model="state.userForm.username" />
                    </el-form-item>
                    <el-form-item label="初始密码">
                      <el-input v-model="state.userForm.password" type="password" show-password />
                    </el-form-item>
                    <el-form-item label="姓名">
                      <el-input v-model="state.userForm.name" />
                    </el-form-item>
                    <el-form-item label="企业微信 UserID（可选）">
                      <el-input v-model="state.userForm.wecom_userid" placeholder="用于关联企业微信员工身份" />
                      <p class="field-hint">用于补全部门、关联企业微信员工；后台登录仍使用账号密码。</p>
                    </el-form-item>
                    <el-form-item label="部门">
                      <el-input v-model="state.userForm.department" />
                    </el-form-item>
                    <el-form-item label="角色">
                      <el-select v-model="state.userForm.roles" multiple>
                        <el-option label="管理员" value="admin" />
                        <el-option label="行政制票" value="hr" />
                        <el-option label="饭堂核销" value="verifier" />
                        <el-option label="行政查看" value="auditor" />
                      </el-select>
                    </el-form-item>
                  </div>
                  <div class="form-actions">
                    <el-button type="primary" @click="createUser"><Plus :size="16" /> 创建用户</el-button>
                  </div>
                </el-form>
              </el-tab-pane>
            </el-tabs>
          </section>
        </section>

      </section>
    </main>
  `,
}

createApp(App).use(ElementPlus, { locale: zhCn }).mount('#app')
