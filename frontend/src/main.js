import ElementPlus, { ElMessage, ElMessageBox } from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { computed, createApp, reactive } from 'vue/dist/vue.esm-bundler.js'
import {
  BadgeCheck,
  CalendarDays,
  ChevronDown,
  ClipboardList,
  CreditCard,
  Download,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  QrCode,
  RefreshCw,
  Save,
  Search,
  Settings,
  ShieldCheck,
  Utensils,
  X,
} from 'lucide-vue-next'
import axios from 'axios'
import './style.css'

const api = axios.create({ baseURL: '/api' })
const isTicketPage = location.pathname.startsWith('/ticket')
const isMyCardPage = location.pathname.startsWith('/my-card')
const weekdayOptions = [
  { label: '周一', value: 0 },
  { label: '周二', value: 1 },
  { label: '周三', value: 2 },
  { label: '周四', value: 3 },
  { label: '周五', value: 4 },
  { label: '周六', value: 5 },
  { label: '周日', value: 6 },
]

const state = reactive({
  token: localStorage.getItem('token') || '',
  me: null,
  isMyCardPage,
  activeView: 'tickets',
  login: { username: '', password: '' },
  tickets: [],
  ticketOverviewStats: {
    total: 0,
    statuses: { unused: 0, used: 0, expired: 0, void: 0 },
    meals: {
      breakfast: { count: 0, used: 0 },
      lunch: { count: 0, used: 0 },
      dinner: { count: 0, used: 0 },
    },
  },
  selectedTicketIds: [],
  users: [],
  userMode: 'list',
  settings: [],
  settingsForm: {},
  cardUsers: [],
  cardUserFilters: { keyword: '', binding_status: '' },
  cardUserPagination: { page: 1, page_size: 20, total: 0 },
  cardUserStats: { total: 0, bound: 0, unbound: 0 },
  cardUserSort: { prop: '', order: '' },
  wanoaOptions: [],
  wanoaOptionLoading: false,
  externalUserSyncing: false,
  externalUserSyncMessage: '',
  lowBalancePreviewLoading: false,
  lowBalancePreview: null,
  bindingDialog: {
    visible: false,
    row: null,
    selected_wanoa_pin: '',
  },
  logType: 'sync',
  syncLogs: [],
  accessLogs: [],
  auditLogs: [],
  syncLogFilters: { source: '', status: '' },
  accessLogFilters: { result: '', keyword: '' },
  auditLogFilters: { action: '', target_type: '', keyword: '' },
  logPagination: { page: 1, page_size: 20, total: 0 },
  filters: { status: '', keyword: '', date_preset: '', meal_date_from: '', meal_date_to: '' },
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
  resetPasswordDialog: {
    visible: false,
    row: null,
    password: '',
  },
  myCard: {
    loading: false,
    error: '',
    data: null,
    oauthUrl: '',
  },
  publicBrand: {
    company_name: '公司名称',
    footer_text: '版权归IT部门所有',
  },
  mealWindows: {
    timezone: 'Asia/Shanghai',
    breakfast: '06:00-09:00',
    lunch: '11:00-13:30',
    dinner: '17:00-19:30',
  },
  clockNow: Date.now(),
  publicToken: isTicketPage
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
  sidebarCollapsed: localStorage.getItem('sidebarCollapsed') === '1',
  navGroupOpen: {},
  loading: false,
  saving: false,
})

let scanLocked = false
setInterval(() => {
  state.clockNow = Date.now()
}, 30 * 1000)

api.interceptors.request.use((config) => {
  if (state.token) config.headers.Authorization = `Bearer ${state.token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = apiErrorMessage(error)
    if (error.response?.status === 401) {
      state.token = ''
      state.me = null
      localStorage.removeItem('token')
      if (state.verifyToken && isVerifyRequest(error)) {
        state.loginError = '请先使用饭堂核销员账号登录，登录后会继续处理当前二维码'
      }
    }
    if (!error.config?.silentError) {
      ElMessage.error(message)
    }
    return Promise.reject(error)
  }
)

function apiErrorMessage(error, fallback = '请求处理失败') {
  if (!error.response) {
    return '网络请求失败，请检查手机网络、系统访问地址或服务器状态'
  }
  const status = error.response.status
  const detail = error.response.data?.detail
  if (status === 401) return '请先使用饭堂核销员账号登录后再扫码核销'
  if (status === 403) return '当前账号没有饭堂核销权限，请联系管理员分配核销员角色'
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => item?.msg || item?.message || '')
      .filter(Boolean)
      .join('；') || fallback
  }
  if (status === 404) return '二维码不存在，请确认是否扫描了本系统生成的饭票二维码'
  return fallback
}

function isVerifyRequest(error) {
  return String(error.config?.url || '').includes('/tickets/verify')
}

function hasRole(...roles) {
  return Boolean(state.me?.roles?.some((role) => roles.includes(role)))
}

function formatMeal(type) {
  return { breakfast: '早餐', lunch: '午餐', dinner: '晚餐' }[type] || type
}

function parseMealWindow(value) {
  const text = String(value || '').trim()
  const parts = text.split(/\s*(?:-|~|至|到)\s*/, 2)
  if (parts.length !== 2) return null
  const start = clockToMinutes(parts[0])
  const end = clockToMinutes(parts[1])
  if (start === null || end === null) return null
  return { start, end, text: `${minutesToClock(start)}-${minutesToClock(end)}` }
}

function clockToMinutes(value) {
  const match = String(value || '').trim().match(/^([01]?\d|2[0-3]):([0-5]\d)$/)
  if (!match) return null
  return Number(match[1]) * 60 + Number(match[2])
}

function minutesToClock(value) {
  const hour = Math.floor(value / 60)
  const minute = value % 60
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
}

function currentMinutesInTimezone(timestamp, timezone) {
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: timezone || 'Asia/Shanghai',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(new Date(timestamp))
  const hour = Number(parts.find((item) => item.type === 'hour')?.value || 0)
  const minute = Number(parts.find((item) => item.type === 'minute')?.value || 0)
  return hour * 60 + minute
}

function windowContainsMinute(window, minute) {
  if (window.end >= window.start) return window.start <= minute && minute <= window.end
  return minute >= window.start || minute <= window.end
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

function formatWeekday(value) {
  return weekdayOptions.find((item) => item.value === Number(value))?.label || '周一'
}

function formatAlertSchedule(preview) {
  if (!preview) return '-'
  const weekendText = preview.weekend_enabled ? '，含周末' : '，周末不推送'
  if (preview.frequency === 'weekly') {
    return `每${formatWeekday(preview.weekday)} ${preview.push_time}${weekendText}`
  }
  return `每天 ${preview.push_time}${weekendText}`
}

function formatNextPush(row) {
  if (row.due) return '现在'
  return row.next_push_at ? formatDateTime(row.next_push_at) : '周末不推送'
}

function statusTag(status) {
  return { unused: 'warning', used: 'success', expired: 'info', void: 'danger' }[status] || 'info'
}

function sourceLabel(source) {
  return { manual: '手工', batch: '批量', wecom: '企微审批', wecom_approval: '企微审批' }[source] || source
}

function formatAuditAction(action) {
  return { low_balance_alert_push: '低余额提醒推送' }[action] || action
}

function formatRoles(roles) {
  const labels = { admin: '管理员', hr: '行政制票', verifier: '饭堂核销', auditor: '行政查看' }
  return (roles || []).map((role) => labels[role] || role).join(' / ')
}

function formatDetail(detail) {
  if (!detail || !Object.keys(detail).length) return '-'
  if ('balance' in detail && 'threshold' in detail && 'result' in detail) {
    const result = detail.result === 'success' ? '成功' : '失败'
    const name = detail.name || detail.card_no || '-'
    const balance = formatCurrency(detail.balance)
    const threshold = formatCurrency(detail.threshold)
    return `${result} · ${name} · 余额 ${balance} / 阈值 ${threshold}`
  }
  return JSON.stringify(detail)
}

function formatMoney(value) {
  if (value === null || value === undefined || value === '') return '-'
  const amount = Number(value)
  if (Number.isNaN(amount)) return value
  return amount.toFixed(2)
}

function formatCurrency(value) {
  const amount = formatMoney(value)
  return amount === '-' ? '-' : `￥${amount}`
}

function formatDateInput(value) {
  const date = new Date(value)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function cleanParams(params) {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== '' && value !== null && value !== undefined),
  )
}

function ticketFilterParams() {
  const { date_preset: datePreset, ...params } = state.filters
  void datePreset
  return cleanParams(params)
}

function setTicketDatePreset(preset) {
  state.filters.date_preset = preset
  if (!preset) {
    state.filters.meal_date_from = ''
    state.filters.meal_date_to = ''
    return
  }
  const now = new Date()
  let start = new Date(now)
  let end = new Date(now)
  if (preset === 'week') {
    const day = now.getDay() || 7
    start = new Date(now)
    start.setDate(now.getDate() - day + 1)
    end = new Date(start)
    end.setDate(start.getDate() + 6)
  } else if (preset === 'month') {
    start = new Date(now.getFullYear(), now.getMonth(), 1)
    end = new Date(now.getFullYear(), now.getMonth() + 1, 0)
  }
  state.filters.meal_date_from = formatDateInput(start)
  state.filters.meal_date_to = formatDateInput(end)
}

function clearTicketDatePreset() {
  state.filters.date_preset = ''
}

function isNavGroupActive(item) {
  return Boolean(item.children?.some((child) => child.key === state.activeView))
}

function isNavGroupOpen(item) {
  return !item.children || state.navGroupOpen[item.key] !== false
}

function openParentForView(key) {
  for (const item of navItems.value) {
    if (item.children?.some((child) => child.key === key)) {
      state.navGroupOpen[item.key] = true
    }
  }
}

function setDefaultView() {
  if (hasRole('admin', 'hr', 'auditor')) {
    state.activeView = 'dashboard'
    return
  }
  if (hasRole('verifier')) state.activeView = 'verify'
}

const navItems = computed(() =>
  [
    hasRole('admin', 'hr', 'auditor') && {
      key: 'ticketGroup',
      label: '饭票业务',
      icon: QrCode,
      subtitle: '饭票全流程',
      children: [
        { key: 'dashboard', label: '数据总览', subtitle: '首页大屏' },
        { key: 'tickets', label: '饭票记录', subtitle: '查询、作废、导出' },
        hasRole('admin', 'hr') && { key: 'create', label: '饭票生成', subtitle: '单张饭票' },
      ].filter(Boolean),
    },
    hasRole('verifier') && {
      key: 'verify',
      label: '扫码核销',
      icon: BadgeCheck,
      subtitle: '饭堂核销',
    },
    hasRole('admin', 'hr', 'auditor') && {
      key: 'cardGroup',
      label: '饭卡管理',
      icon: CreditCard,
      subtitle: '企微与万傲绑定',
      children: [
        { key: 'cardUsers', label: '企微用户绑定', subtitle: '用户表、饭卡映射' },
      ],
    },
    hasRole('admin', 'hr', 'auditor') && {
      key: 'opsGroup',
      label: '系统运维',
      icon: ClipboardList,
      subtitle: '设置、权限、日志',
      children: [
        hasRole('admin') && { key: 'settings', label: '系统设置', subtitle: '接口与规则' },
        hasRole('admin') && { key: 'users', label: '权限管理', subtitle: '账号与角色' },
        { key: 'logs', label: '日志中心', subtitle: '同步、访问、操作' },
      ].filter(Boolean),
    },
  ].filter(Boolean)
)

const activeTitle = computed(() => {
  for (const item of navItems.value) {
    if (item.key === state.activeView) return item.label
    const child = item.children?.find((entry) => entry.key === state.activeView)
    if (child) return child.label
  }
  return '后台管理'
})

const activeMealWindowText = computed(() => {
  const rows = [
    { key: 'breakfast', label: '早餐', value: state.mealWindows.breakfast },
    { key: 'lunch', label: '午餐', value: state.mealWindows.lunch },
    { key: 'dinner', label: '晚餐', value: state.mealWindows.dinner },
  ]
    .map((item) => ({ ...item, window: parseMealWindow(item.value) }))
    .filter((item) => item.window)
  if (!rows.length) return '核销时段：未配置'
  const nowMinutes = currentMinutesInTimezone(state.clockNow, state.mealWindows.timezone)
  const active = rows.find((item) => windowContainsMinute(item.window, nowMinutes))
  if (active) return `核销时段：${active.label} ${active.window.text}`
  const next = [...rows]
    .sort((a, b) => {
      const offsetA = (a.window.start - nowMinutes + 1440) % 1440
      const offsetB = (b.window.start - nowMinutes + 1440) % 1440
      return offsetA - offsetB
    })[0]
  return `非核销时段 · 下一时段：${next.label} ${next.window.text}`
})

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

const dashboardBars = computed(() => {
  const meals = [
    { key: 'breakfast', label: '早餐' },
    { key: 'lunch', label: '午餐' },
    { key: 'dinner', label: '晚餐' },
  ]
  const counts = meals.map((meal) => state.ticketOverviewStats.meals[meal.key]?.count || 0)
  const max = Math.max(1, ...counts)
  return meals.map((meal, index) => {
    const count = counts[index]
    const used = state.ticketOverviewStats.meals[meal.key]?.used || 0
    return {
      ...meal,
      count,
      used,
      percent: Math.max(8, Math.round((count / max) * 100)),
      rate: count ? Math.round((used / count) * 100) : 0,
    }
  })
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
  await loadMealWindows()
  if (hasRole('admin', 'hr', 'auditor')) {
    await loadTickets()
    await loadTicketOverviewStats()
    await loadCardUserStats()
  }
  if (hasRole('admin')) {
    await loadSettings()
    await loadUsers()
  }
  if (hasRole('admin', 'hr', 'auditor')) await loadCardUsers()
  if (state.verifyToken && hasRole('admin', 'verifier')) {
    state.activeView = 'verify'
    await processScannedText(state.verifyToken)
  } else if (state.verifyToken) {
    state.activeView = 'verify'
    state.verifyResult = {
      type: 'danger',
      title: '无法核销',
      message: '当前账号没有饭堂核销权限，请使用核销员账号登录或联系管理员分配权限',
    }
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
  openParentForView(key)
  state.mobileNavOpen = false
  if (key === 'dashboard' && !state.tickets.length) loadTickets()
  if (key === 'dashboard') {
    loadTicketOverviewStats()
    loadCardUserStats()
  }
  if (key === 'tickets' && !state.tickets.length) loadTickets()
  if (key === 'settings' && !state.settings.length) loadSettings()
  if (key === 'users' && !state.users.length) loadUsers()
  if (key === 'cardUsers') {
    if (!state.cardUsers.length) loadCardUsers()
  }
  if (key === 'logs') loadLogs()
}

function handleNavParent(item) {
  if (!item.children) {
    switchView(item.key)
    return
  }
  if (state.sidebarCollapsed) {
    state.sidebarCollapsed = false
    localStorage.setItem('sidebarCollapsed', '0')
  }
  state.navGroupOpen[item.key] = !isNavGroupOpen(item)
}

function toggleSidebarCollapsed() {
  state.sidebarCollapsed = !state.sidebarCollapsed
  state.mobileNavOpen = false
  localStorage.setItem('sidebarCollapsed', state.sidebarCollapsed ? '1' : '0')
}

async function loadTickets() {
  if (!hasRole('admin', 'hr', 'auditor')) return
  state.loading = true
  try {
    const res = await api.get('/tickets', {
      params: {
        ...ticketFilterParams(),
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

async function loadTicketOverviewStats() {
  if (!hasRole('admin', 'hr', 'auditor')) return
  const res = await api.get('/tickets/stats')
  state.ticketOverviewStats = {
    total: res.data.total || 0,
    statuses: {
      unused: res.data.statuses?.unused || 0,
      used: res.data.statuses?.used || 0,
      expired: res.data.statuses?.expired || 0,
      void: res.data.statuses?.void || 0,
    },
    meals: {
      breakfast: res.data.meals?.breakfast || { count: 0, used: 0 },
      lunch: res.data.meals?.lunch || { count: 0, used: 0 },
      dinner: res.data.meals?.dinner || { count: 0, used: 0 },
    },
  }
}

async function searchTickets() {
  state.pagination.page = 1
  await loadTickets()
}

async function resetFilters() {
  state.filters.keyword = ''
  state.filters.status = ''
  state.filters.date_preset = ''
  state.filters.meal_date_from = ''
  state.filters.meal_date_to = ''
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
  state.publicBrand.company_name = state.settingsForm.ticket_company_name || state.publicBrand.company_name
  state.publicBrand.footer_text = state.settingsForm.ticket_footer_text || state.publicBrand.footer_text
  applyMealWindowsFromSettings()
}

async function loadMealWindows() {
  const res = await api.get('/settings/public-meal-windows')
  state.mealWindows = {
    timezone: res.data.timezone || 'Asia/Shanghai',
    breakfast: res.data.breakfast || '',
    lunch: res.data.lunch || '',
    dinner: res.data.dinner || '',
  }
}

function applyMealWindowsFromSettings() {
  state.mealWindows = {
    timezone: state.settingsForm.app_timezone || state.mealWindows.timezone || 'Asia/Shanghai',
    breakfast: state.settingsForm.meal_window_breakfast || '',
    lunch: state.settingsForm.meal_window_lunch || '',
    dinner: state.settingsForm.meal_window_dinner || '',
  }
}

async function saveSettings() {
  state.saving = true
  try {
    const res = await api.put('/settings', { values: state.settingsForm })
    state.settings = res.data
    state.settingsForm = Object.fromEntries(res.data.map((item) => [item.key, item.value || '']))
    applyMealWindowsFromSettings()
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
  await loadTicketOverviewStats()
}

async function loadUsers() {
  if (!hasRole('admin')) return
  const res = await api.get('/auth/users')
  state.users = res.data
}

async function createUser() {
  if (!state.userForm.username || !state.userForm.password || !state.userForm.name) {
    ElMessage.warning('请填写账号、初始密码和姓名')
    return
  }
  if (state.userForm.password.length < 8) {
    ElMessage.warning('初始密码至少 8 位')
    return
  }
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
  if (!row.name || !row.roles?.length) {
    ElMessage.warning('姓名和角色不能为空')
    return
  }
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

function openResetPasswordDialog(row) {
  state.resetPasswordDialog.visible = true
  state.resetPasswordDialog.row = row
  state.resetPasswordDialog.password = ''
}

function closeResetPasswordDialog() {
  state.resetPasswordDialog.visible = false
  state.resetPasswordDialog.row = null
  state.resetPasswordDialog.password = ''
}

async function resetUserPassword() {
  const row = state.resetPasswordDialog.row
  const password = state.resetPasswordDialog.password
  if (!row) return
  if (!password || password.length < 8) {
    ElMessage.warning('新密码至少 8 位')
    return
  }
  await api.post(`/auth/users/${row.id}/reset-password`, { password })
  ElMessage.success('密码已重置')
  closeResetPasswordDialog()
}

async function loadCardUsers() {
  if (!hasRole('admin', 'hr', 'auditor')) return
  const res = await api.get('/integrations/users/wecom-bindings', {
      params: {
        ...state.cardUserFilters,
        sort_by: state.cardUserSort.prop || undefined,
        sort_order: state.cardUserSort.order || undefined,
        page: state.cardUserPagination.page,
        page_size: state.cardUserPagination.page_size,
      },
  })
  state.cardUsers = res.data.items.map((item) => ({
    ...item,
  }))
  state.cardUserPagination.total = res.data.total
  state.cardUserPagination.page = res.data.page
  state.cardUserPagination.page_size = res.data.page_size
}

async function loadCardUserStats() {
  if (!hasRole('admin', 'hr', 'auditor')) return
  const [totalRes, boundRes, unboundRes] = await Promise.all([
    api.get('/integrations/users/wecom-bindings', { params: { page: 1, page_size: 1 } }),
    api.get('/integrations/users/wecom-bindings', {
      params: { binding_status: 'bound', page: 1, page_size: 1 },
    }),
    api.get('/integrations/users/wecom-bindings', {
      params: { binding_status: 'unbound', page: 1, page_size: 1 },
    }),
  ])
  state.cardUserStats.total = totalRes.data.total || 0
  state.cardUserStats.bound = boundRes.data.total || 0
  state.cardUserStats.unbound = unboundRes.data.total || 0
}

async function changeCardUserPage(page) {
  state.cardUserPagination.page = page
  await loadCardUsers()
}

async function searchCardUsers() {
  state.cardUserPagination.page = 1
  await loadCardUsers()
}

async function setCardBindingStatus(status) {
  state.cardUserFilters.binding_status = status
  await searchCardUsers()
}

async function handleCardUserSortChange({ prop, order }) {
  state.cardUserSort.prop = prop || ''
  state.cardUserSort.order = order || ''
  state.cardUserPagination.page = 1
  await loadCardUsers()
}

function runOnEnter(event, action) {
  if (event.key === 'Enter') action()
}

function onTicketKeywordKeyup(event) {
  runOnEnter(event, searchTickets)
}

function onCardUserKeywordKeyup(event) {
  runOnEnter(event, searchCardUsers)
}

function onLogSearchKeyup(event) {
  runOnEnter(event, searchLogs)
}

async function syncAllExternalUsers() {
  if (state.externalUserSyncing) return
  state.externalUserSyncing = true
  state.externalUserSyncMessage = '正在同步企业微信、万傲用户并刷新饭卡余额...'
  ElMessage.info(state.externalUserSyncMessage)
  try {
    const res = await api.post('/integrations/users/sync/all')
    const message = res.data.message || `已同步 ${res.data.total || 0} 个用户`
    state.externalUserSyncMessage = message
    ElMessage.success(message)
    await loadCardUsers()
    await loadCardUserStats()
    if (state.activeView === 'logs' && state.logType === 'sync') await loadLogs()
  } finally {
    state.externalUserSyncing = false
  }
}

async function previewLowBalanceAlerts() {
  state.lowBalancePreviewLoading = true
  try {
    const res = await api.get('/integrations/users/low-balance-alert/preview', {
      params: {
        threshold: state.settingsForm.low_balance_alert_threshold || undefined,
        frequency: state.settingsForm.low_balance_alert_frequency || undefined,
        weekday: state.settingsForm.low_balance_alert_weekday || undefined,
        push_time: state.settingsForm.low_balance_alert_time || undefined,
        weekend_enabled: state.settingsForm.low_balance_alert_weekend_enabled || undefined,
        title: state.settingsForm.low_balance_alert_title || undefined,
        content: state.settingsForm.low_balance_alert_content || undefined,
      },
    })
    state.lowBalancePreview = res.data
    ElMessage.success(
      `命中 ${res.data.total || 0} 人，${formatAlertSchedule(res.data)} 应推送 ${res.data.due_total || 0} 人`
    )
  } finally {
    state.lowBalancePreviewLoading = false
  }
}

async function searchWanoaOptions(keyword) {
  const text = String(keyword || '').trim()
  if (!text) {
    state.wanoaOptions = []
    return
  }
  state.wanoaOptionLoading = true
  try {
    const res = await api.get('/integrations/users/candidates', {
      params: {
        source: 'wanoa',
        keyword: text,
        page: 1,
        page_size: 20,
      },
    })
    state.wanoaOptions = res.data.items
  } finally {
    state.wanoaOptionLoading = false
  }
}

function openBindingDialog(row) {
  state.bindingDialog.row = row
  state.bindingDialog.selected_wanoa_pin = row.wanoa_pin || ''
  state.wanoaOptions = []
  if (row.wanoa_pin) {
    state.wanoaOptions = [{
      external_id: row.wanoa_pin,
      name: row.wanoa_name,
      department_name: row.wanoa_department,
      card_no: row.wanoa_card_no,
    }]
  }
  state.bindingDialog.visible = true
}

function closeBindingDialog() {
  state.bindingDialog.visible = false
  state.bindingDialog.row = null
  state.bindingDialog.selected_wanoa_pin = ''
  state.wanoaOptions = []
}

async function bindWanoaUser() {
  const row = state.bindingDialog.row
  if (!row) return
  if (!state.bindingDialog.selected_wanoa_pin) {
    ElMessage.warning('请选择万傲用户')
    return
  }
  await api.post('/integrations/users/bindings', {
    wecom_userid: row.wecom_userid,
    wanoa_pin: state.bindingDialog.selected_wanoa_pin,
  })
  ElMessage.success('饭卡用户绑定已保存')
  closeBindingDialog()
  await loadCardUsers()
  await loadCardUserStats()
}

function formatWanoaOption(option) {
  return [
    option.name,
    option.external_id,
    option.department_name,
    option.card_no ? `卡号 ${option.card_no}` : '',
  ].filter(Boolean).join(' / ')
}

async function loadLogs() {
  if (!hasRole('admin', 'hr', 'auditor')) return
  const params = {
    page: state.logPagination.page,
    page_size: state.logPagination.page_size,
  }
  let endpoint = '/logs/sync'
  if (state.logType === 'sync') {
    Object.assign(params, state.syncLogFilters)
  } else if (state.logType === 'access') {
    endpoint = '/logs/access'
    Object.assign(params, state.accessLogFilters)
  } else {
    endpoint = '/logs/audit'
    Object.assign(params, state.auditLogFilters)
  }
  const res = await api.get(endpoint, { params })
  if (state.logType === 'sync') state.syncLogs = res.data.items
  if (state.logType === 'access') state.accessLogs = res.data.items
  if (state.logType === 'audit') state.auditLogs = res.data.items
  state.logPagination.total = res.data.total
  state.logPagination.page = res.data.page
  state.logPagination.page_size = res.data.page_size
}

async function changeLogType(type) {
  state.logType = type
  state.logPagination.page = 1
  await loadLogs()
}

async function changeLogPage(page) {
  state.logPagination.page = page
  await loadLogs()
}

async function searchLogs() {
  state.logPagination.page = 1
  await loadLogs()
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
  await loadTicketOverviewStats()
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
  await loadTicketOverviewStats()
}

async function previewTicket(options = {}) {
  const token = state.verifyToken.trim()
  if (!token) {
    ElMessage.warning('请输入二维码 token')
    return
  }
  const res = await api.get('/tickets/verify/preview', {
    params: { token },
    silentError: options.silentError,
  })
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
  await loadTicketOverviewStats()
}

async function processScannedText(text) {
  if (scanLocked) return
  scanLocked = true
  const token = extractTokenFromScan(text)
  state.verifyToken = token
  state.verifyPreview = null
  if (!token) {
    state.verifyResult = {
      type: 'danger',
      title: '核销失败',
      message: '二维码内容为空，请重新扫描饭票二维码',
    }
    scanLocked = false
    return
  }
  state.verifyResult = {
    type: '',
    title: '正在核销',
    message: '已识别二维码，正在读取饭票信息',
  }
  try {
    await previewTicket({ silentError: true })
    await api.post('/tickets/verify/consume', { token }, { silentError: true })
    await previewTicket({ silentError: true })
    await loadTicketOverviewStats()
    state.verifyResult = {
      type: 'success',
      title: '核销成功',
      message: '饭票状态已更新为已核销',
    }
    ElMessage.success('饭票核销成功')
  } catch (error) {
    try {
      await previewTicket({ silentError: true })
    } catch {
      state.verifyPreview = null
    }
    state.verifyResult = {
      type: 'danger',
      title: '核销失败',
      message: apiErrorMessage(error, '二维码无法核销'),
    }
  } finally {
    setTimeout(() => {
      scanLocked = false
    }, 1000)
  }
}

async function exportReport() {
  const res = await api.get('/reports/tickets.xlsx', {
    responseType: 'blob',
    params: ticketFilterParams(),
  })
  const url = URL.createObjectURL(res.data)
  const link = document.createElement('a')
  link.href = url
  link.download = 'meal-tickets.xlsx'
  link.click()
  URL.revokeObjectURL(url)
}

function myCardRedirectUri() {
  const url = new URL(location.href)
  url.searchParams.delete('code')
  url.searchParams.delete('state')
  return url.toString()
}

async function loadPublicBrand() {
  try {
    const res = await api.get('/settings/public-brand')
    state.publicBrand.company_name = res.data.company_name || state.publicBrand.company_name
    state.publicBrand.footer_text = res.data.footer_text || state.publicBrand.footer_text
  } catch {
    // Public brand is decorative; keep defaults if the request fails.
  }
}

async function loadMyCard() {
  state.myCard.loading = true
  state.myCard.error = ''
  await loadPublicBrand()
  const params = new URLSearchParams(location.search)
  const code = params.get('code')
  try {
    if (!code) {
      const res = await api.get('/wecom/oauth-url', {
        params: { redirect_uri: myCardRedirectUri() },
      })
      if (!res.data?.url) throw new Error('企业微信授权地址生成失败')
      state.myCard.oauthUrl = res.data.url
      location.replace(res.data.url)
      return
    }
    const res = await api.get('/wecom/card-balance', { params: { code } })
    if (res.data?.status !== 'success') {
      throw new Error(res.data?.message || '读取饭卡余额失败，请从企业微信自建应用重新打开')
    }
    state.myCard.data = res.data
  } catch (error) {
    state.myCard.error =
      error.response?.data?.detail || error.message || '读取饭卡余额失败，请从企业微信自建应用重新打开'
  } finally {
    state.myCard.loading = false
  }
}

if (state.isMyCardPage) {
  loadMyCard()
} else if (!state.publicToken) {
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
    ChevronDown,
    ClipboardList,
    CreditCard,
    Download,
    LogOut,
    Menu,
    PanelLeftClose,
    PanelLeftOpen,
    Plus,
    QrCode,
    RefreshCw,
    Save,
    Search,
    Settings,
    ShieldCheck,
    Utensils,
    X,
  },
  setup() {
    return {
      state,
      navItems,
      weekdayOptions,
      activeTitle,
      activeMealWindowText,
      ticketStats,
      dashboardBars,
      canManageTickets,
      roleDefinitions,
      hasRole,
      login,
      logout,
      switchView,
      loadTickets,
      searchTickets,
      resetFilters,
      setTicketDatePreset,
      clearTicketDatePreset,
      changePage,
      changePageSize,
      loadSettings,
      saveSettings,
      loadUsers,
      createUser,
      saveUser,
      openResetPasswordDialog,
      closeResetPasswordDialog,
      resetUserPassword,
      loadCardUsers,
      changeCardUserPage,
      handleCardUserSortChange,
      setCardBindingStatus,
      syncAllExternalUsers,
      previewLowBalanceAlerts,
      searchWanoaOptions,
      bindWanoaUser,
      loadLogs,
      changeLogType,
      changeLogPage,
      searchLogs,
      createTicket,
      voidTicket,
      handleTicketSelectionChange,
      voidSelectedTickets,
      previewTicket,
      consumeTicket,
      exportReport,
      loadMyCard,
      formatMeal,
      formatStatus,
      formatDateTime,
      formatAlertSchedule,
      formatNextPush,
      statusTag,
      sourceLabel,
      formatAuditAction,
      formatRoles,
      formatDetail,
      formatMoney,
      formatCurrency,
      formatWanoaOption,
      isNavGroupActive,
      isNavGroupOpen,
      handleNavParent,
      toggleSidebarCollapsed,
      openBindingDialog,
      closeBindingDialog,
      onTicketKeywordKeyup,
      onCardUserKeywordKeyup,
      onLogSearchKeyup,
    }
  },
  template: `
    <main v-if="state.isMyCardPage" class="my-card-page">
      <section class="my-card-shell">
        <div class="my-card-head">
          <span class="soft-pill">企业微信自建应用</span>
          <h1>我的饭卡</h1>
          <strong class="mobile-company-name">{{ state.publicBrand.company_name }}</strong>
        </div>

        <section v-if="state.myCard.loading" class="mobile-card-panel balance-loading">
          <RefreshCw :size="28" />
          <strong>正在读取饭卡余额</strong>
        </section>

        <section v-else-if="state.myCard.error" class="mobile-card-panel balance-error">
          <ShieldCheck :size="34" />
          <strong>无法读取饭卡</strong>
          <span>{{ state.myCard.error }}</span>
          <a v-if="state.myCard.oauthUrl" class="mobile-primary-action" :href="state.myCard.oauthUrl">
            重新授权
          </a>
        </section>

        <template v-else-if="state.myCard.data">
          <section class="balance-hero-card" :class="{ warning: Number(state.myCard.data.balance || 0) < 50 }">
            <span>当前饭卡余额</span>
            <strong>{{ formatCurrency(state.myCard.data.balance) }}</strong>
          </section>

          <section class="mobile-card-panel identity-panel">
            <h2>{{ state.myCard.data.wecom_name || state.myCard.data.wecom_userid }}</h2>
            <dl>
              <div>
                <dt>企业微信 UserID</dt>
                <dd>{{ state.myCard.data.wecom_userid || '-' }}</dd>
              </div>
              <div>
                <dt>部门</dt>
                <dd>{{ state.myCard.data.wecom_department || '-' }}</dd>
              </div>
              <div>
                <dt>万傲用户</dt>
                <dd>{{ state.myCard.data.wanoa_name ? state.myCard.data.wanoa_name + ' / ' + state.myCard.data.wanoa_pin : '-' }}</dd>
              </div>
              <div>
                <dt>饭卡号</dt>
                <dd>{{ state.myCard.data.wanoa_card_no || '-' }}</dd>
              </div>
            </dl>
          </section>

          <section class="mobile-card-panel">
            <h2>同步状态</h2>
            <dl>
              <div>
                <dt>余额状态</dt>
                <dd>{{ state.myCard.data.balance_status || state.myCard.data.status }}</dd>
              </div>
              <div>
                <dt>最近同步</dt>
                <dd>{{ formatDateTime(state.myCard.data.last_balance_at) }}</dd>
              </div>
              <div>
                <dt>本次刷新</dt>
                <dd>{{ formatDateTime(state.myCard.data.refreshed_at) }}</dd>
              </div>
              <div>
                <dt>提示</dt>
                <dd>{{ state.myCard.data.balance_message || '-' }}</dd>
              </div>
            </dl>
          </section>
        </template>

        <footer class="mobile-copyright">{{ state.publicBrand.footer_text }}</footer>
      </section>
    </main>

    <main v-else-if="state.publicToken" class="ticket-page">
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
        <div v-if="state.verifyToken" class="login-notice">
          已识别到饭票二维码，请使用饭堂核销员账号登录，登录后将自动继续核销。
        </div>
        <el-form label-position="top" autocomplete="off" @submit.prevent>
          <el-form-item label="账号">
            <el-input v-model="state.login.username" autocomplete="off" name="meal-ticket-login-user" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input
              v-model="state.login.password"
              type="password"
              autocomplete="new-password"
              name="meal-ticket-login-pass"
              show-password
            />
          </el-form-item>
          <div v-if="state.loginError" class="login-error">{{ state.loginError }}</div>
          <el-button type="primary" class="full" @click="login">
            <ShieldCheck :size="16" /> 登录
          </el-button>
        </el-form>
      </section>
    </main>

    <main v-else class="app-shell" :class="{ collapsed: state.sidebarCollapsed }">
      <div
        v-if="state.mobileNavOpen"
        class="mobile-backdrop"
        @click="state.mobileNavOpen = false"
      ></div>
      <aside class="sidebar" :class="{ open: state.mobileNavOpen, collapsed: state.sidebarCollapsed }">
        <div class="brand-line compact">
          <Utensils :size="24" />
          <strong>饭票核销</strong>
          <button class="sidebar-close" type="button" @click="state.mobileNavOpen = false">
            <X :size="18" />
          </button>
        </div>
        <nav>
          <div v-for="item in navItems" :key="item.key" class="nav-block">
            <template v-if="item.children">
              <button
                type="button"
                class="nav-title-button"
                :class="{ open: isNavGroupOpen(item) }"
                :title="item.label"
                @click="handleNavParent(item)"
              >
                <span>{{ item.label }}</span>
                <ChevronDown class="nav-caret" :size="14" />
              </button>
              <div v-if="isNavGroupOpen(item) && !state.sidebarCollapsed" class="sub-nav">
                <button
                  v-for="child in item.children"
                  :key="child.key"
                  type="button"
                  class="sub-nav-item"
                  :class="{ active: state.activeView === child.key }"
                  :title="child.label"
                  @click="switchView(child.key)"
                >
                  <span class="nav-dot"></span>
                  <span>
                    <strong>{{ child.label }}</strong>
                  </span>
                </button>
              </div>
            </template>
            <button
              v-else
              type="button"
              class="nav-parent"
              :class="{ active: state.activeView === item.key, expanded: isNavGroupActive(item), open: isNavGroupOpen(item), grouped: item.children }"
              :title="item.label"
              @click="handleNavParent(item)"
            >
              <component :is="item.icon" :size="18" />
              <span>
                <strong>{{ item.label }}</strong>
              </span>
              <ChevronDown v-if="item.children" class="nav-caret" :size="16" />
            </button>
          </div>
        </nav>
      </aside>

      <section class="workspace">
        <header class="topbar">
          <div class="topbar-title">
            <el-button class="mobile-menu-button" circle @click="state.mobileNavOpen = true">
              <Menu :size="18" />
            </el-button>
            <el-button class="desktop-collapse-button" circle @click="toggleSidebarCollapsed">
              <PanelLeftOpen v-if="state.sidebarCollapsed" :size="18" />
              <PanelLeftClose v-else :size="18" />
            </el-button>
            <div>
              <h1>{{ activeTitle }}</h1>
              <p>{{ state.me?.name }} · {{ formatRoles(state.me?.roles) }}</p>
            </div>
          </div>
          <div class="top-actions">
            <span v-if="state.activeView !== 'verify'" class="soft-pill">今日同步成功</span>
            <span v-if="state.activeView !== 'verify'" class="soft-pill">{{ activeMealWindowText }}</span>
            <el-button v-if="state.activeView !== 'verify' && hasRole('admin', 'hr')" type="primary" @click="switchView('create')">
              <Plus :size="16" /> 生成饭票
            </el-button>
            <el-button v-if="state.activeView !== 'verify'" @click="logout"><LogOut :size="16" /> 退出</el-button>
          </div>
          <div class="legacy-top-title" aria-hidden="true">
            <h1>{{ activeTitle }}</h1>
            <p>{{ state.me?.name }} · {{ formatRoles(state.me?.roles) }}</p>
          </div>
        </header>

        <section v-if="state.activeView === 'dashboard'" class="content-area dashboard-content">
          <div class="metric-row">
            <section class="metric-card">
              <span>饭票总数</span>
              <strong>{{ state.ticketOverviewStats.total }}</strong>
            </section>
            <section class="metric-card">
              <span>已使用</span>
              <strong>{{ state.ticketOverviewStats.statuses.used }}</strong>
            </section>
            <section class="metric-card">
              <span>未使用</span>
              <strong>{{ state.ticketOverviewStats.statuses.unused }}</strong>
            </section>
            <section class="metric-card">
              <span>饭卡用户</span>
              <strong>{{ state.cardUserStats.total }}</strong>
            </section>
          </div>

          <section class="dashboard-grid">
            <section class="panel dashboard-chart-panel">
              <div class="panel-head">
                <div>
                  <h2>餐别核销进度</h2>
                </div>
                <span class="soft-pill">单位：张</span>
              </div>
              <div class="meal-bars">
                <div v-for="bar in dashboardBars" :key="bar.key" class="meal-bar-row">
                  <div class="meal-bar-meta">
                    <strong>{{ bar.label }}</strong>
                    <span>{{ bar.used }} / {{ bar.count }} · {{ bar.rate }}%</span>
                  </div>
                  <div class="meal-bar-track">
                    <span :style="{ width: bar.percent + '%' }"></span>
                  </div>
                </div>
              </div>
            </section>

            <section class="panel dashboard-side-panel">
              <div class="panel-head">
                <div>
                  <h2>接口健康</h2>
                </div>
              </div>
              <ul class="health-list">
                <li><span>企业微信入口</span><strong>已配置</strong></li>
                <li><span>饭卡余额同步</span><strong>{{ state.cardUserStats.total ? '正常' : '待同步' }}</strong></li>
                <li><span>后台服务</span><strong>运行中</strong></li>
              </ul>
            </section>
          </section>

          <section class="dashboard-grid dashboard-grid-bottom">
            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>最近饭票动态</h2>
                </div>
                <el-button @click="switchView('tickets')">查看记录</el-button>
              </div>
              <ul class="activity-list">
                <li v-for="ticket in state.tickets.slice(0, 5)" :key="ticket.id">
                  <span>{{ formatDateTime(ticket.used_at || ticket.created_at) }} · {{ ticket.employee_name }} · {{ formatMeal(ticket.meal_type) }}</span>
                  <strong>{{ formatStatus(ticket.status) }}</strong>
                </li>
              </ul>
            </section>
            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>饭卡绑定概况</h2>
                </div>
                <el-button @click="switchView('cardUsers')">处理绑定</el-button>
              </div>
              <ul class="activity-list">
                <li>
                  <span>企微用户总数</span>
                  <strong>{{ state.cardUserStats.total }}</strong>
                </li>
                <li>
                  <span>已绑定</span>
                  <strong>{{ state.cardUserStats.bound }}</strong>
                </li>
                <li>
                  <span>未绑定</span>
                  <strong>{{ state.cardUserStats.unbound }}</strong>
                </li>
              </ul>
            </section>
          </section>
        </section>

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

            <div class="filters ticket-filters">
              <el-input
                v-model="state.filters.keyword"
                placeholder="姓名 / UserID / 部门 / 编号 / 审批单"
                clearable
                @keyup="onTicketKeywordKeyup"
              />
              <el-select v-model="state.filters.status" placeholder="状态" clearable>
                <el-option label="未使用" value="unused" />
                <el-option label="已使用" value="used" />
                <el-option label="已过期" value="expired" />
                <el-option label="已作废" value="void" />
              </el-select>
              <div class="date-quick">
                <el-button
                  :class="{ active: !state.filters.date_preset }"
                  @click="setTicketDatePreset('')"
                >
                  全部
                </el-button>
                <el-button
                  :class="{ active: state.filters.date_preset === 'today' }"
                  @click="setTicketDatePreset('today')"
                >
                  今日
                </el-button>
                <el-button
                  :class="{ active: state.filters.date_preset === 'week' }"
                  @click="setTicketDatePreset('week')"
                >
                  本周
                </el-button>
                <el-button
                  :class="{ active: state.filters.date_preset === 'month' }"
                  @click="setTicketDatePreset('month')"
                >
                  本月
                </el-button>
              </div>
              <el-date-picker
                v-model="state.filters.meal_date_from"
                value-format="YYYY-MM-DD"
                type="date"
                placeholder="开始日期"
                @change="clearTicketDatePreset"
              />
              <el-date-picker
                v-model="state.filters.meal_date_to"
                value-format="YYYY-MM-DD"
                type="date"
                placeholder="结束日期"
                @change="clearTicketDatePreset"
              />
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
              <el-table-column v-if="canManageTickets" type="selection" width="40" />
              <el-table-column prop="ticket_no" label="饭票编号" min-width="150" show-overflow-tooltip />
              <el-table-column prop="approval_sp_no" label="审批单号" min-width="135" show-overflow-tooltip />
              <el-table-column prop="employee_name" label="申请人" width="96" />
              <el-table-column prop="department" label="部门" width="92" show-overflow-tooltip />
              <el-table-column label="餐别" width="72">
                <template #default="{ row }">{{ formatMeal(row.meal_type) }}</template>
              </el-table-column>
              <el-table-column label="用餐人" width="74">
                <template #default="{ row }">{{ row.diner_index }} / {{ row.diner_count }}</template>
              </el-table-column>
              <el-table-column prop="meal_date" label="用餐日期" width="108" />
              <el-table-column label="状态" width="96">
                <template #default="{ row }">
                  <el-tag :type="statusTag(row.status)">{{ formatStatus(row.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="核销时间" width="154" show-overflow-tooltip>
                <template #default="{ row }">{{ formatDateTime(row.used_at) }}</template>
              </el-table-column>
              <el-table-column v-if="canManageTickets" label="操作" width="76">
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
            </section>
          </section>
        </section>

        <section v-if="state.activeView === 'cardUsers'" class="content-area">
          <section class="panel">
            <div class="panel-head">
              <div>
                <h2>企微用户绑定</h2>
              </div>
              <div class="head-actions">
                <el-button @click="loadCardUsers"><RefreshCw :size="16" /> 刷新</el-button>
              </div>
            </div>

            <div class="filters card-user-filters">
              <el-input
                v-model="state.cardUserFilters.keyword"
                placeholder="搜索企微用户：姓名 / UserID / 部门"
                clearable
                @keyup="onCardUserKeywordKeyup"
              />
              <div class="binding-filter-tabs">
                <button
                  type="button"
                  :class="{ active: !state.cardUserFilters.binding_status }"
                  @click="setCardBindingStatus('')"
                >全部</button>
                <button
                  type="button"
                  :class="{ active: state.cardUserFilters.binding_status === 'bound' }"
                  @click="setCardBindingStatus('bound')"
                >已绑定</button>
                <button
                  type="button"
                  :class="{ active: state.cardUserFilters.binding_status === 'unbound' }"
                  @click="setCardBindingStatus('unbound')"
                >未绑定</button>
              </div>
              <el-button type="primary" @click="searchCardUsers"><Search :size="16" /> 查询</el-button>
            </div>

            <el-table :data="state.cardUsers" stripe @sort-change="handleCardUserSortChange">
              <el-table-column prop="wecom_name" label="企微姓名" width="104" sortable="custom" />
              <el-table-column prop="wecom_userid" label="企微 UserID" min-width="132" show-overflow-tooltip sortable="custom" />
              <el-table-column prop="wecom_department" label="企微部门" min-width="128" show-overflow-tooltip sortable="custom" />
              <el-table-column prop="wanoa_name" label="已绑定万傲用户" min-width="158" show-overflow-tooltip sortable="custom">
                <template #default="{ row }">
                  {{ row.wanoa_name ? row.wanoa_name + ' / ' + row.wanoa_pin : '-' }}
                </template>
              </el-table-column>
              <el-table-column prop="wanoa_department" label="万傲部门" width="116" show-overflow-tooltip sortable="custom" />
              <el-table-column prop="wanoa_card_no" label="饭卡号" width="124" show-overflow-tooltip sortable="custom" />
              <el-table-column prop="last_balance" label="饭卡余额" width="112" sortable="custom">
                <template #default="{ row }">
                  {{ formatMoney(row.last_balance) }}
                </template>
              </el-table-column>
              <el-table-column prop="binding_status" label="状态" width="88" sortable="custom">
                <template #default="{ row }">
                  <el-tag
                    class="clickable-tag"
                    :type="row.binding_status === 'active' ? 'success' : 'info'"
                    @click="setCardBindingStatus(row.binding_status === 'active' ? 'bound' : 'unbound')"
                  >
                    {{ row.binding_status === 'active' ? '已绑定' : '未绑定' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column v-if="hasRole('admin')" label="操作" width="92">
                <template #default="{ row }">
                  <el-button type="primary" plain size="small" @click="openBindingDialog(row)">
                    {{ row.binding_status === 'active' ? '重绑' : '绑定' }}
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
            <div class="pagination-bar">
              <el-pagination
                v-model:current-page="state.cardUserPagination.page"
                :page-size="state.cardUserPagination.page_size"
                :total="state.cardUserPagination.total"
                layout="total, prev, pager, next"
                @current-change="changeCardUserPage"
              />
            </div>
          </section>

          <el-dialog
            v-model="state.bindingDialog.visible"
            title="绑定万傲用户"
            width="520px"
            class="binding-dialog"
            @closed="closeBindingDialog"
          >
            <section v-if="state.bindingDialog.row" class="binding-summary">
              <div>
                <span>企微用户</span>
                <strong>{{ state.bindingDialog.row.wecom_name }} / {{ state.bindingDialog.row.wecom_userid }}</strong>
              </div>
              <div>
                <span>企微部门</span>
                <strong>{{ state.bindingDialog.row.wecom_department || '-' }}</strong>
              </div>
              <div>
                <span>当前绑定</span>
                <strong>
                  {{ state.bindingDialog.row.wanoa_name ? state.bindingDialog.row.wanoa_name + ' / ' + state.bindingDialog.row.wanoa_pin : '未绑定' }}
                </strong>
              </div>
            </section>

            <el-form label-position="top">
              <el-form-item label="选择万傲用户">
                <el-select
                  v-model="state.bindingDialog.selected_wanoa_pin"
                  filterable
                  remote
                  reserve-keyword
                  clearable
                  :remote-method="searchWanoaOptions"
                  :loading="state.wanoaOptionLoading"
                  placeholder="输入万傲用户名搜索"
                >
                  <el-option
                    v-for="option in state.wanoaOptions"
                    :key="option.external_id"
                    :label="formatWanoaOption(option)"
                    :value="option.external_id"
                  />
                </el-select>
              </el-form-item>
            </el-form>

            <template #footer>
              <el-button @click="state.bindingDialog.visible = false">取消</el-button>
              <el-button type="primary" @click="bindWanoaUser">
                <Save :size="14" /> 保存绑定
              </el-button>
            </template>
          </el-dialog>
        </section>

        <section v-if="state.activeView === 'logs'" class="content-area">
          <section class="panel">
            <div class="panel-head">
              <div>
                <h2>日志中心</h2>
              </div>
              <el-button @click="loadLogs"><RefreshCw :size="16" /> 刷新</el-button>
            </div>

            <el-radio-group
              v-model="state.logType"
              class="log-switch"
              @change="changeLogType"
            >
              <el-radio-button label="sync">同步记录</el-radio-button>
              <el-radio-button label="access">访问记录</el-radio-button>
              <el-radio-button label="audit">操作记录</el-radio-button>
            </el-radio-group>

            <div v-if="state.logType === 'sync'" class="filters">
              <el-select v-model="state.syncLogFilters.source" placeholder="同步来源" clearable>
                <el-option label="全部同步" value="all" />
                <el-option label="万傲" value="wanoa" />
                <el-option label="企业微信" value="wecom" />
              </el-select>
              <el-select v-model="state.syncLogFilters.status" placeholder="同步状态" clearable>
                <el-option label="成功" value="success" />
                <el-option label="失败" value="failed" />
                <el-option label="运行中" value="running" />
              </el-select>
              <el-button type="primary" @click="searchLogs"><Search :size="16" /> 查询</el-button>
            </div>

            <div v-if="state.logType === 'access'" class="filters">
              <el-select v-model="state.accessLogFilters.result" placeholder="访问结果" clearable>
                <el-option label="成功" value="success" />
                <el-option label="失败" value="failed" />
              </el-select>
              <el-input
                v-model="state.accessLogFilters.keyword"
                placeholder="饭票编号 / 申请人 / 原因 / IP"
                clearable
                @keyup="onLogSearchKeyup"
              />
              <el-button type="primary" @click="searchLogs"><Search :size="16" /> 查询</el-button>
            </div>

            <div v-if="state.logType === 'audit'" class="filters">
              <el-input
                v-model="state.auditLogFilters.action"
                placeholder="操作动作"
                clearable
                @keyup="onLogSearchKeyup"
              />
              <el-input
                v-model="state.auditLogFilters.target_type"
                placeholder="对象类型"
                clearable
                @keyup="onLogSearchKeyup"
              />
              <el-input
                v-model="state.auditLogFilters.keyword"
                placeholder="关键字"
                clearable
                @keyup="onLogSearchKeyup"
              />
              <el-button type="primary" @click="searchLogs"><Search :size="16" /> 查询</el-button>
            </div>

            <el-table v-if="state.logType === 'sync'" :data="state.syncLogs" stripe>
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column label="来源" width="110">
                <template #default="{ row }">
                  {{ row.source === 'all' ? '全部' : row.source === 'wanoa' ? '万傲' : row.source === 'wecom' ? '企业微信' : row.source }}
                </template>
              </el-table-column>
              <el-table-column label="状态" width="110">
                <template #default="{ row }">
                  <el-tag :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'">
                    {{ row.status === 'success' ? '成功' : row.status === 'failed' ? '失败' : '运行中' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="total" label="数量" width="100" />
              <el-table-column prop="message" label="消息" min-width="260" show-overflow-tooltip />
              <el-table-column label="开始时间" min-width="170">
                <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
              </el-table-column>
              <el-table-column label="结束时间" min-width="170">
                <template #default="{ row }">{{ formatDateTime(row.finished_at) }}</template>
              </el-table-column>
            </el-table>

            <el-table v-if="state.logType === 'access'" :data="state.accessLogs" stripe>
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="ticket_no" label="饭票编号" min-width="150" show-overflow-tooltip />
              <el-table-column prop="verifier_name" label="访问账号" width="120" />
              <el-table-column label="结果" width="100">
                <template #default="{ row }">
                  <el-tag :type="row.result === 'success' ? 'success' : 'danger'">
                    {{ row.result === 'success' ? '成功' : '失败' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="reason" label="原因" min-width="220" show-overflow-tooltip />
              <el-table-column prop="ip" label="IP" min-width="130" show-overflow-tooltip />
              <el-table-column prop="user_agent" label="User-Agent" min-width="240" show-overflow-tooltip />
              <el-table-column label="时间" min-width="170">
                <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
              </el-table-column>
            </el-table>

            <el-table v-if="state.logType === 'audit'" :data="state.auditLogs" stripe>
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="actor_name" label="操作人" width="120" />
              <el-table-column label="动作" min-width="150" show-overflow-tooltip>
                <template #default="{ row }">{{ formatAuditAction(row.action) }}</template>
              </el-table-column>
              <el-table-column prop="target_type" label="对象类型" min-width="130" show-overflow-tooltip />
              <el-table-column prop="target_id" label="对象ID" min-width="130" show-overflow-tooltip />
              <el-table-column label="详情" min-width="260" show-overflow-tooltip>
                <template #default="{ row }">{{ formatDetail(row.detail) }}</template>
              </el-table-column>
              <el-table-column label="时间" min-width="170">
                <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
              </el-table-column>
            </el-table>

            <div class="pagination-bar">
              <el-pagination
                v-model:current-page="state.logPagination.page"
                :page-size="state.logPagination.page_size"
                :total="state.logPagination.total"
                layout="total, prev, pager, next"
                @current-change="changeLogPage"
              />
            </div>
          </section>
        </section>

        <section v-if="state.activeView === 'settings'" class="content-area">
          <section class="panel">
            <div class="panel-head">
              <div>
                <h2>系统设置</h2>
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
                      placeholder="版权归IT部门所有"
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
                <h3>万傲瑞达</h3>
                <el-form label-position="top">
                  <el-form-item label="平台地址">
                    <el-input v-model="state.settingsForm.wanoa_base_url" placeholder="https://wanoa.example.com" />
                  </el-form-item>
                  <el-form-item label="授权用户名 ID">
                    <el-input v-model="state.settingsForm.wanoa_client_id" placeholder="api-user" />
                  </el-form-item>
                  <el-form-item label="接口 access_token">
                    <el-input v-model="state.settingsForm.wanoa_client_secret" type="password" show-password />
                  </el-form-item>
                  <el-form-item label="人员列表接口路径">
                    <el-input v-model="state.settingsForm.wanoa_person_list_path" />
                  </el-form-item>
                  <el-form-item label="饭卡接口路径">
                    <el-input v-model="state.settingsForm.wanoa_card_list_path" />
                  </el-form-item>
                  <el-form-item label="同步分页大小">
                    <el-input v-model="state.settingsForm.wanoa_sync_page_size" />
                  </el-form-item>
                  <el-form-item label="启用定时同步">
                    <el-switch
                      v-model="state.settingsForm.external_user_sync_enabled"
                      active-value="true"
                      inactive-value="false"
                    />
                  </el-form-item>
                  <el-form-item label="同步间隔分钟">
                    <el-input v-model="state.settingsForm.external_user_sync_interval_minutes" />
                  </el-form-item>
                  <el-form-item label="启用自动绑定">
                    <el-switch
                      v-model="state.settingsForm.external_user_auto_bind_enabled"
                      active-value="true"
                      inactive-value="false"
                    />
                  </el-form-item>
                  <el-form-item label="立即同步用户">
                    <el-button
                      v-if="hasRole('admin')"
                      type="primary"
                      :loading="state.externalUserSyncing"
                      @click="syncAllExternalUsers"
                    >
                      <RefreshCw :size="16" /> 同步企业微信与万傲
                    </el-button>
                    <p v-if="state.externalUserSyncMessage" class="field-hint">
                      {{ state.externalUserSyncMessage }}
                    </p>
                  </el-form-item>
                </el-form>
              </section>

              <section class="settings-panel low-balance-panel">
                <h3>低余额提醒</h3>
                <el-form label-position="top">
                  <el-form-item label="启用提醒">
                    <el-switch
                      v-model="state.settingsForm.low_balance_alert_enabled"
                      active-value="true"
                      inactive-value="false"
                    />
                  </el-form-item>
                  <el-form-item label="判断金额">
                    <el-input v-model="state.settingsForm.low_balance_alert_threshold" placeholder="20" />
                  </el-form-item>
                  <el-form-item label="推送周期">
                    <el-radio-group v-model="state.settingsForm.low_balance_alert_frequency">
                      <el-radio-button label="daily">每天</el-radio-button>
                      <el-radio-button label="weekly">每周</el-radio-button>
                    </el-radio-group>
                  </el-form-item>
                  <el-form-item
                    v-if="state.settingsForm.low_balance_alert_frequency === 'weekly'"
                    label="推送星期"
                  >
                    <el-select v-model="state.settingsForm.low_balance_alert_weekday">
                      <el-option
                        v-for="item in weekdayOptions"
                        :key="item.value"
                        :label="item.label"
                        :value="item.value"
                      />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="推送时间">
                    <el-time-picker
                      v-model="state.settingsForm.low_balance_alert_time"
                      format="HH:mm"
                      value-format="HH:mm"
                      placeholder="11:00"
                    />
                  </el-form-item>
                  <el-form-item label="周末推送">
                    <el-switch
                      v-model="state.settingsForm.low_balance_alert_weekend_enabled"
                      active-value="true"
                      inactive-value="false"
                      active-text="允许"
                      inactive-text="过滤"
                    />
                  </el-form-item>
                  <el-form-item label="标题模板">
                    <el-input v-model="state.settingsForm.low_balance_alert_title" placeholder="饭卡余额提醒" />
                  </el-form-item>
                  <el-form-item label="内容模板">
                    <el-input
                      v-model="state.settingsForm.low_balance_alert_content"
                      type="textarea"
                      :rows="4"
                      placeholder="{name}，你的饭卡余额为 {balance} 元，低于 {threshold} 元，请及时处理。"
                    />
                  </el-form-item>
                  <div class="variable-row">
                    <span>{name}</span>
                    <span>{balance}</span>
                    <span>{threshold}</span>
                    <span>{department}</span>
                    <span>{card_no}</span>
                    <span>{now}</span>
                  </div>
                  <div class="form-actions compact-actions">
                    <el-button
                      :loading="state.lowBalancePreviewLoading"
                      @click="previewLowBalanceAlerts"
                    >
                      <Search :size="16" /> 测试条件
                    </el-button>
                  </div>
                </el-form>
                <div v-if="state.lowBalancePreview" class="preview-result">
                  <div class="preview-summary">
                    <span>命中 {{ state.lowBalancePreview.total }} 人</span>
                    <strong>{{ formatAlertSchedule(state.lowBalancePreview) }} 应推送 {{ state.lowBalancePreview.due_total }} 人</strong>
                  </div>
                  <el-table :data="state.lowBalancePreview.items" max-height="260" stripe>
                    <el-table-column prop="name" label="用户" width="100" show-overflow-tooltip />
                    <el-table-column prop="department" label="部门" width="110" show-overflow-tooltip />
                    <el-table-column label="余额" width="92">
                      <template #default="{ row }">{{ formatCurrency(row.balance) }}</template>
                    </el-table-column>
                    <el-table-column label="预计推送" width="154" show-overflow-tooltip>
                      <template #default="{ row }">{{ formatNextPush(row) }}</template>
                    </el-table-column>
                    <el-table-column prop="content" label="内容" min-width="220" show-overflow-tooltip />
                  </el-table>
                </div>
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
                    <template #default="{ row }"><el-input v-model="row.wecom_userid" placeholder="企业微信 UserID" /></template>
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
                  <el-table-column label="操作" width="176" fixed="right">
                    <template #default="{ row }">
                      <el-button type="primary" plain size="small" @click="saveUser(row)">
                        <Save :size="14" /> 保存
                      </el-button>
                      <el-button plain size="small" @click="openResetPasswordDialog(row)">
                        重置密码
                      </el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </el-tab-pane>

              <el-tab-pane label="新增用户" name="create">
                <div class="role-grid">
                  <section v-for="role in roleDefinitions" :key="role.code" class="role-card">
                    <strong>{{ role.label }}</strong>
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
                      <el-input v-model="state.userForm.wecom_userid" placeholder="企业微信 UserID" />
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

            <el-dialog
              v-model="state.resetPasswordDialog.visible"
              title="重置密码"
              width="420px"
              append-to-body
              @close="closeResetPasswordDialog"
            >
              <el-form label-position="top" @submit.prevent>
                <el-form-item label="账号">
                  <el-input :model-value="state.resetPasswordDialog.row?.username || ''" disabled />
                </el-form-item>
                <el-form-item label="新密码">
                  <el-input
                    v-model="state.resetPasswordDialog.password"
                    type="password"
                    show-password
                    autocomplete="new-password"
                  />
                </el-form-item>
              </el-form>
              <template #footer>
                <el-button @click="closeResetPasswordDialog">取消</el-button>
                <el-button type="primary" @click="resetUserPassword">保存</el-button>
              </template>
            </el-dialog>
          </section>
        </section>

      </section>
    </main>
  `,
}

createApp(App).use(ElementPlus, { locale: zhCn }).mount('#app')
