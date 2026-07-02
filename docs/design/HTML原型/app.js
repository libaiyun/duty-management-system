const menuGroups = [
  { title: '工作台', items: [{ id: 'dashboard', icon: '▦', label: '首页' }] },
  { title: '我的值班', items: [
    { id: 'mySchedule', icon: '日', label: '我的排班' },
    { id: 'swapMine', icon: '换', label: '换班申请' },
    { id: 'leaveMine', icon: '假', label: '请假申请' },
    { id: 'coverMine', icon: '顶', label: '我的顶班' }
  ]},
  { title: '审批中心', items: [
    { id: 'todoApproval', icon: '审', label: '待办审批' },
    { id: 'doneApproval', icon: '办', label: '已办审批' }
  ]},
  { title: '排班管理', items: [
    { id: 'monthlySchedule', icon: '排', label: '月度排班' },
    { id: 'scheduleDetail', icon: '表', label: '排班明细' },
    { id: 'actualDuty', icon: '实', label: '实际值班' }
  ]},
  { title: '请假顶班', items: [
    { id: 'leaveRecords', icon: '记', label: '请假记录' },
    { id: 'coverArrange', icon: '安', label: '顶班安排' }
  ]},
  { title: '退费管理', items: [
    { id: 'refundCalc', icon: '算', label: '退费计算' },
    { id: 'refundDetail', icon: '细', label: '退费明细' }
  ]},
  { title: '考勤报表', items: [
    { id: 'attendance', icon: '勤', label: '月度考勤' },
    { id: 'exportHistory', icon: '导', label: '导出历史' }
  ]},
  { title: '基础资料', items: [
    { id: 'stations', icon: '站', label: '台站机房' },
    { id: 'people', icon: '人', label: '人员管理' },
    { id: 'rules', icon: '规', label: '班次规则' },
    { id: 'holiday', icon: '节', label: '节假日与标准' }
  ]},
  { title: '系统管理', items: [
    { id: 'accounts', icon: '账', label: '账号角色' },
    { id: 'logs', icon: '志', label: '操作日志' },
    { id: 'backup', icon: '备', label: '备份归档' }
  ]}
];

const rows = {
  todo: [
    ['换班审批', 'HB20260701001', '谢燃', '7月3日 晚班', badge('待主任审批','pending'), '09:18', action('审批')],
    ['请假审批', 'QJ20260701003', '杨婷', '7月5日 中班', badge('待主任审批','pending'), '10:02', action('审批')],
    ['顶班确认', 'DB20260701002', '郑昌军', '7月6日 早班', badge('待顶班确认','info'), '11:31', action('查看')]
  ],
  schedule: [
    ['2026-07', '广发台', '主城区机房', '广播发射台轮班', '93', '10', badge('已发布','ok'), '2026-06-25 09:00', action('查看明细')],
    ['2026-07', '广发台', '北山机房', '广播发射台轮班', '93', '8', badge('草稿','pending'), '2026-06-26 14:12', action('发布')],
    ['2026-06', '广发台', '主城区机房', '广播发射台轮班', '90', '10', badge('已锁定','lock'), '2026-05-26 08:40', action('导出')]
  ],
  swap: [
    ['HB20260701001', '单向替班', '谢燃', '7月3日 晚班', '陈浪', '-', badge('待主任审批','pending'), '2026-07-01 09:18', action('查看')],
    ['HB20260628004', '互换', '王小瑜', '7月4日 中班', '李军', '7月8日 中班', badge('已生效','ok'), '2026-06-28 16:21', action('详情')]
  ],
  leave: [
    ['QJ20260701003', '事假', '杨婷', '7月5日', '中班', badge('待主任审批','pending'), badge('未安排','bad'), '2026-07-01 10:02', action('查看')],
    ['QJ20260630006', '公休假', '朱小平', '7月2日', '早班', badge('已通过','ok'), badge('已确认','ok'), '2026-06-30 12:20', action('详情')]
  ],
  cover: [
    ['DB20260701002', 'QJ20260630006', '朱小平', '7月2日', '早班', '周岱', badge('待顶班确认','pending'), action('确认')],
    ['DB20260629001', 'QJ20260629002', '李军', '7月1日', '中班', '郑昌军', badge('已生效','ok'), action('详情')]
  ],
  actual: [
    ['7月1日', '早班', '谢燃、朱小平', '谢燃、朱小平', '原排班', '否', badge('正常','ok')],
    ['7月2日', '早班', '谢燃、朱小平', '谢燃、周岱', '顶班', '否', badge('已变更','info')],
    ['7月3日', '晚班', '曾建豪、黄宇', '曾建豪、陈浪', '换班', '否', badge('待生效','pending')],
    ['7月1日', '晚班', '谢燃、朱小平', '谢燃、朱小平', '原排班', '是', badge('节假日','info')]
  ],
  refundBatch: [
    ['TF202607', '2026-07', '广发台', '主城区机房', '餐补退费', '¥128.00', '12', badge('已计算','info'), action('查看明细')],
    ['TF202607-FD', '2026-07', '广发台', '主城区机房', '节假日加班费退费', '¥672.00', '12', badge('已复核','ok'), action('锁定')]
  ],
  refundDetail: [
    ['餐补退费', '7月1日', '晚班', '朱小平', '杨婷', '¥4.00', '中班承担部分晚班', '原排班'],
    ['节假日加班费退费', '7月1日', '晚班', '谢燃', '李军', '¥56.00', '3小时/8小时折算', '法定节假日'],
    ['餐补退费', '7月2日', '早班', '周岱', '朱小平', '¥4.00', '顶班关联', '顶班']
  ],
  attendance: [
    ['谢燃', '主城区机房', '8', '0', '8', '0', '0', '16', badge('正常','ok'), action('明细')],
    ['朱小平', '主城区机房', '7', '0', '7', '0', '1', '14', badge('请假','pending'), action('明细')],
    ['周岱', '主城区机房', '1', '0', '0', '1', '0', '2', badge('顶班','info'), action('明细')]
  ],
  exports: [
    ['DC20260701001', '月度值班表', '2026-07-广发台主城区值班表.xlsx', '2026-07', badge('成功','ok'), '机房主任', '2026-07-01 11:20', action('下载')],
    ['DC20260701002', '退费汇总表', '2026-07-退费汇总.xlsx', '2026-07', badge('生成中','pending'), '财务统计', '2026-07-01 11:28', action('查看')]
  ],
  people: [
    ['P001', '谢燃', '值机员', '广发台', '主城区机房', '是', '1', badge('已绑定','ok'), badge('启用','ok'), action('编辑')],
    ['P002', '朱小平', '值机员', '广发台', '主城区机房', '是', '2', badge('已绑定','ok'), badge('启用','ok'), action('编辑')],
    ['P009', '周岱', '检修班', '广发台', '主城区机房', '否', '-', badge('已绑定','ok'), badge('启用','ok'), action('编辑')]
  ],
  logs: [
    ['LOG20260701001', '排班管理', '发布排班', '2026-07 主城区机房', '机房主任', '2026-07-01 09:00', badge('成功','ok'), action('详情')],
    ['LOG20260701002', '审批中心', '同意请假', 'QJ20260630006', '机房主任', '2026-07-01 09:35', badge('成功','ok'), action('详情')]
  ]
};

const pages = {
  dashboard: page('工作台首页', '展示当前用户的待办、值班、排班和退费概览。', renderDashboard),
  mySchedule: page('我的排班', '查看本人月度排班，并从班次发起换班或请假。', () => renderMySchedule()),
  swapMine: page('换班申请', '发起、确认、撤回和查看换班流程。', () => renderListPage({ type:'swap', title:'换班申请', actions:['新增换班'], filters:['月份','换班类型','状态','目标人员'], headers:['申请单号','换班类型','申请人','原班次','目标人员','目标班次','状态','提交时间','操作'], rows: rows.swap, flow:['草稿','待对方确认','待主任审批','已生效'] })),
  leaveMine: page('请假申请', '提交公休假、事假、病假申请并跟踪顶班状态。', () => renderListPage({ type:'leave', title:'请假申请', actions:['新增请假'], filters:['月份','请假类型','审批状态','顶班状态'], headers:['申请单号','请假类型','申请人','日期','班次','审批状态','顶班状态','提交时间','操作'], rows: rows.leave, flow:['草稿','待主任审批','待安排顶班','待顶班确认','已完成'] })),
  coverMine: page('我的顶班', '顶班人确认或拒绝主任安排的顶班任务。', () => renderListPage({ title:'我的顶班', actions:['确认顶班'], filters:['月份','状态','班次','原值机员'], headers:['顶班单号','请假单号','原值机员','日期','班次','顶班人','状态','操作'], rows: rows.cover, flow:['待安排','待顶班人确认','已确认','已生效'] })),
  todoApproval: page('待办审批', '机房主任处理换班、请假审批事项。', () => renderListPage({ title:'待办审批', actions:['批量查看'], filters:['业务类型','申请人','到达时间','机房'], headers:['待办类型','业务单号','申请人','班次日期','状态','到达时间','操作'], rows: rows.todo, flow:['查看业务','填写意见','同意/拒绝','业务回写'] })),
  doneApproval: page('已办审批', '查询当前用户已经处理的审批历史。', () => renderListPage({ title:'已办审批', actions:['导出'], filters:['业务类型','审批结果','申请人','处理时间'], headers:['审批编号','业务类型','业务单号','申请人','审批结果','审批意见','处理时间','操作'], rows: [['SP20260601','换班审批','HB20260628004','王小瑜',badge('同意','ok'),'同意调整','2026-06-28 17:02',action('详情')], ['SP20260602','请假审批','QJ20260630006','朱小平',badge('同意','ok'),'安排顶班','2026-06-30 14:18',action('详情')]] })),
  monthlySchedule: page('月度排班', '按台站、机房、月份生成、发布、导出和锁定排班。', () => renderListPage({ title:'月度排班', actions:['生成排班','发布','导出 Excel'], filters:['台站','机房','月份','状态'], headers:['月份','台站','机房','排班规则','班次数','人员数','状态','生成时间','操作'], rows: rows.schedule, flow:['未生成','草稿','已发布','已锁定'] })),
  scheduleDetail: page('排班明细', '查看和编辑每日早中晚三班排班。', renderScheduleDetail),
  actualDuty: page('实际值班', '汇总排班、换班、请假、顶班后的实际值班结果。', () => renderListPage({ title:'实际值班', actions:['重新同步','导出'], filters:['月份','日期','班次','人员','变更来源'], headers:['日期','班次','原排班人员','实际值班人员','变更来源','是否节假日','状态'], rows: rows.actual })),
  leaveRecords: page('请假记录', '主任查看本机房请假审批与顶班完成情况。', () => renderListPage({ title:'请假记录', actions:['登记请假','安排顶班','导出'], filters:['月份','申请人','请假类型','审批状态','顶班状态'], headers:['申请单号','请假类型','申请人','日期','班次','审批状态','顶班状态','提交时间','操作'], rows: rows.leave })),
  coverArrange: page('顶班安排', '机房主任为获批请假的班次安排顶班人员。', () => renderTwoPane('待安排请假', '顶班安排表单', rows.cover)),
  refundCalc: page('退费计算', '计算餐补退费和法定节假日加班费退费批次。', () => renderListPage({ title:'退费计算', actions:['计算','复核','锁定','导出 Excel'], filters:['台站','机房','月份','退费类型','状态'], headers:['批次号','月份','台站','机房','退费类型','应退总额','人数','状态','操作'], rows: rows.refundBatch, flow:['未计算','已计算','已复核','已锁定','已导出'] })),
  refundDetail: page('退费明细', '查看退费明细表和人员汇总表。', () => renderRefundDetail()),
  attendance: page('月度考勤', '按实际值班生成月度考勤汇总并导出 Excel。', () => renderListPage({ title:'月度考勤', actions:['生成考勤','锁定','导出 Excel'], filters:['台站','机房','月份','人员','是否异常'], headers:['人员','所属机房','早班','中班','晚班','顶班','请假','总次数','状态','操作'], rows: rows.attendance })),
  exportHistory: page('导出历史', '保留值班表、考勤表和退费表的导出记录。', () => renderListPage({ title:'导出历史', actions:['重新生成'], filters:['文件类型','月份','导出人','状态'], headers:['导出编号','文件类型','文件名称','月份','状态','导出人','导出时间','操作'], rows: rows.exports })),
  stations: page('台站机房', '维护台站、机房和组织层级。', () => renderTwoPane('组织树', '台站机房列表', [['ORG001','广发台','台站','-', '郑昌军', badge('启用','ok'), action('编辑')], ['ORG002','主城区机房','机房','广发台','郑昌军', badge('启用','ok'), action('编辑')]])),
  people: page('人员管理', '维护值机员、检修班、主任、副主任档案和排班属性。', () => renderListPage({ title:'人员管理', actions:['新增人员','绑定账号','导入','导出'], filters:['姓名','人员类型','台站','机房','账号状态'], headers:['人员编号','姓名','人员类型','台站','机房','参与排班','轮班顺序','账号状态','人员状态','操作'], rows: rows.people })),
  rules: page('班次规则', '维护班次定义、双岗值人数和广播发射台轮班规则。', renderRules),
  holiday: page('节假日与标准', '维护法定节假日并展示固定补贴退费标准。', renderHoliday),
  accounts: page('账号角色', '管理账号、角色、菜单权限、数据范围和微信绑定状态。', () => renderListPage({ title:'账号角色', actions:['新增账号','分配角色','重置密码'], filters:['账号','角色','台站','机房','状态'], headers:['账号','绑定人员','角色','台站范围','机房范围','微信绑定','状态','最后登录','操作'], rows: [['director','郑昌军','机房主任','广发台','主城区机房',badge('已绑定','ok'),badge('启用','ok'),'2026-07-01 08:55',action('编辑')], ['admin','系统管理员','系统管理员','全部','全部',badge('未绑定','pending'),badge('启用','ok'),'2026-07-01 08:20',action('编辑')]] })),
  logs: page('操作日志', '查询排班调整、审批、导出和配置变更记录。', () => renderListPage({ title:'操作日志', actions:['导出'], filters:['模块','操作类型','操作人','时间范围'], headers:['日志编号','模块','操作类型','操作对象','操作人','操作时间','结果','操作'], rows: rows.logs })),
  backup: page('备份归档', '查看备份记录、月份归档和恢复申请。', () => renderListPage({ title:'备份归档', actions:['手动备份','归档月份','恢复申请'], filters:['类型','月份','台站','状态'], headers:['记录编号','类型','月份','台站','机房','执行时间','执行人','状态','操作'], rows: [['BK20260701001','自动备份','2026-07','广发台','全部','2026-07-01 02:00','系统',badge('成功','ok'),action('下载')], ['GD202606','月份归档','2026-06','广发台','主城区机房','2026-07-01 09:40','系统管理员',badge('已锁定','lock'),action('详情')]] }))
};

function badge(text, type='info') { return `<span class="status ${type}">${text}</span>`; }
function action(text) { return `<span class="actions"><button class="btn subtle" data-action="openDrawer">${text}</button></span>`; }
function page(title, desc, render) { return { title, desc, render }; }

function renderMenu() {
  const menu = document.querySelector('#menu');
  menu.innerHTML = menuGroups.map(group => `<div class="menu-group"><div class="menu-group-title">${group.title}</div>${group.items.map(item => `<button data-page="${item.id}"><span>${item.icon}</span><span class="label">${item.label}</span></button>`).join('')}</div>`).join('');
}

function navigate(id) {
  const pageData = pages[id] || pages.dashboard;
  document.querySelectorAll('[data-page]').forEach(btn => btn.classList.toggle('active', btn.dataset.page === id));
  const group = menuGroups.find(g => g.items.some(i => i.id === id));
  const item = group?.items.find(i => i.id === id);
  document.querySelector('#breadcrumb').textContent = `${group?.title || '工作台'} / ${item?.label || pageData.title}`;
  document.querySelector('#pageHost').innerHTML = `
    <section class="page-head">
      <div><h1>${pageData.title}</h1><p>${pageData.desc}</p></div>
      <div class="toolbar"><button class="btn subtle" data-action="toast">刷新</button><button class="btn primary" data-action="openModal">页面说明</button></div>
    </section>
    ${pageData.render()}
  `;
}

function renderDashboard() {
  return `
    <section class="grid cols-4">
      <div class="panel stat"><span>今日值班</span><strong>早班</strong><small>谢燃、朱小平 00:00-08:00</small></div>
      <div class="panel stat teal"><span>待办审批</span><strong>3</strong><small>换班 1，请假 1，顶班 1</small></div>
      <div class="panel stat amber"><span>本月排班</span><strong>已发布</strong><small>2026-07 主城区机房</small></div>
      <div class="panel stat danger"><span>退费批次</span><strong>¥800</strong><small>2 个批次待锁定</small></div>
    </section>
    <section class="grid cols-2">
      <div class="panel"><h2>待办事项</h2>${table(['类型','单号','申请人','班次','状态','到达','操作'], rows.todo)}</div>
      <div class="panel"><h2>状态流转</h2>${flow(['排班发布','换班审批','顶班确认','实际值班更新','退费/考勤计算'])}<div class="empty">首期审批在系统内完成，微信小程序作为后续扩展。</div></div>
    </section>`;
}

function renderMySchedule() {
  const days = Array.from({ length: 14 }, (_, i) => {
    const d = i + 1;
    const holiday = d === 1;
    return `<div class="day"><div class="date">7月${d}日</div><div class="shift ${holiday ? 'holiday' : ''}"><span>早班</span><b>${d % 3 === 0 ? '曾建豪 黄宇' : '谢燃 朱小平'}</b></div><div class="shift"><span>中班</span><b>${d % 2 ? '李军 杨婷' : '陈浪 王小瑜'}</b></div><div class="shift ${holiday ? 'holiday' : ''}"><span>晚班</span><b>${d % 3 === 0 ? '曾建豪 黄宇' : '谢燃 朱小平'}</b></div><button class="btn subtle" data-action="openModal">发起</button></div>`;
  }).join('');
  return `<section class="panel"><div class="filters">${filterFields(['月份','班次','状态'])}<button class="btn primary">查询</button><button class="btn subtle" data-action="openModal">发起换班</button><button class="btn subtle" data-action="openModal">发起请假</button></div></section><section class="calendar">${days}</section>`;
}

function renderScheduleDetail() {
  return `<section class="panel"><div class="filters">${filterFields(['日期范围','班次','人员','异常类型'])}<button class="btn primary">查询</button><button class="btn subtle" data-action="openModal">编辑班次</button><button class="btn subtle" data-action="toast">导出</button></div></section><section class="panel">${table(['日期','星期','节假日','早班人员','中班人员','晚班人员','异常','操作'], [['7月1日','三','是','谢燃、朱小平','李军、杨婷','谢燃、朱小平',badge('节假日','info'),action('编辑')],['7月2日','四','否','谢燃、朱小平','陈浪、王小瑜','曾建豪、黄宇',badge('正常','ok'),action('编辑')],['7月3日','五','否','曾建豪、黄宇','李军、王小瑜','曾建豪、黄宇',badge('待换班','pending'),action('编辑')]])}</section>`;
}

function renderRefundDetail() {
  return `<section class="panel"><div class="tabs"><button class="tab active">明细表</button><button class="tab">人员汇总表</button><button class="tab">异常说明</button></div>${table(['退费类型','日期','班次','应退人员','应收人员','金额','来源原因','关联业务'], rows.refundDetail)}</section>`;
}

function renderRules() {
  return `<section class="panel"><div class="tabs"><button class="tab active">班次定义</button><button class="tab">排班规则</button><button class="tab">规则绑定</button></div>${table(['规则编码','规则名称','适用台站','每班人数','轮班描述','状态','操作'], [['RULE-GFT','广播发射台轮班','广发台','2','晚-早-晚-早休两轮；中-中休两轮',badge('启用','ok'),action('编辑')], ['RULE-SAT','卫星地球站轮班','卫星地球站','2','晚-中-早后休两天半',badge('草稿','pending'),action('编辑')]])}</section>`;
}

function renderHoliday() {
  return `<section class="grid cols-2"><div class="panel"><h2>法定节假日</h2>${table(['日期','名称','年度','是否法定','状态','操作'], [['2026-01-01','元旦','2026','是',badge('启用','ok'),action('编辑')], ['2026-02-17','春节','2026','是',badge('启用','ok'),action('编辑')]])}</div><div class="panel"><h2>固定标准</h2>${table(['项目','标准','说明'], [['早班餐补','10 元/人/班','广播发射台'], ['中班餐补','10 元/人/班','广播发射台'], ['晚班餐补','14 元/人/班','晚班向中班退 4 元'], ['节假日加班费','150 元/人/班','晚班向中班退 56 元']])}</div></section>`;
}

function renderTwoPane(leftTitle, rightTitle, data) {
  return `<section class="two-pane"><div class="panel"><h2>${leftTitle}</h2><div class="org-tree"><button class="active">广发台 / 主城区机房</button><button>广发台 / 北山机房</button><button>卫星地球站 / 运行机房</button></div></div><div class="panel"><h2>${rightTitle}</h2>${table(['编号','类型/来源','人员/名称','日期/上级','班次/负责人','状态','操作'], data)}</div></section>`;
}

function renderListPage(config) {
  return `<section class="panel"><div class="filters">${filterFields(config.filters || ['月份','台站','机房','状态'])}<button class="btn primary">查询</button><button class="btn subtle">重置</button>${(config.actions || []).map(a => `<button class="btn subtle" data-action="openModal">${a}</button>`).join('')}</div></section>${config.flow ? `<section class="panel"><h2>状态流转</h2>${flow(config.flow)}</section>` : ''}<section class="panel">${table(config.headers, config.rows)}</section>`;
}

function filterFields(names) {
  return names.map(name => `<div class="field"><label>${name}</label><input placeholder="请选择/输入${name}"></div>`).join('');
}
function flow(items) { return `<div class="flow">${items.map((item, i) => `<span>${item}</span>${i < items.length - 1 ? '<b>→</b>' : ''}`).join('')}</div>`; }
function table(headers, bodyRows) { return `<div class="table-wrap"><table><thead><tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody>${bodyRows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`; }

function openModal(title='原型操作', body) {
  document.querySelector('#modalTitle').textContent = title;
  document.querySelector('#modalBody').innerHTML = body || `<div class="grid cols-2"><div class="field"><label>台站</label><select><option>广发台</option></select></div><div class="field"><label>机房</label><select><option>主城区机房</option></select></div><div class="field"><label>月份/日期</label><input value="2026-07"></div><div class="field"><label>业务类型</label><select><option>换班</option><option>请假</option><option>顶班</option><option>导出</option></select></div><div class="field" style="grid-column:1/-1"><label>说明</label><textarea placeholder="填写操作说明或审批意见"></textarea></div></div><p class="mini-label">这是 HTML 原型弹窗，用于展示字段、校验和确认动作。</p>`;
  document.querySelector('#modal').hidden = false;
}
function openDrawer() {
  document.querySelector('#drawerTitle').textContent = '业务详情';
  document.querySelector('#drawerBody').innerHTML = `<section class="panel"><h2>基础信息</h2>${table(['字段','值'], [['业务单号','HB20260701001'], ['所属机房','主城区机房'], ['当前状态','待主任审批'], ['申请人','谢燃']])}</section><section class="panel"><h2>审批轨迹</h2><div class="timeline"><div>申请人提交：2026-07-01 09:18</div><div>对方确认同意：2026-07-01 09:35</div><div>等待机房主任审批</div></div></section>`;
  document.querySelector('#drawer').hidden = false;
}
function toast(text='操作已完成，原型数据已模拟更新。') {
  const el = document.querySelector('#toast');
  el.textContent = text;
  el.hidden = false;
  setTimeout(() => el.hidden = true, 2200);
}

document.addEventListener('click', event => {
  const pageButton = event.target.closest('[data-page]');
  if (pageButton) navigate(pageButton.dataset.page);
  const actionButton = event.target.closest('[data-action]');
  if (actionButton) {
    const actionName = actionButton.dataset.action;
    if (actionName === 'openModal') openModal(actionButton.textContent.trim() || '页面说明');
    if (actionName === 'openDrawer') openDrawer();
    if (actionName === 'toast') toast();
  }
  if (event.target.closest('[data-close-modal]')) document.querySelector('#modal').hidden = true;
  if (event.target.closest('[data-confirm-modal]')) { document.querySelector('#modal').hidden = true; toast('已确认，状态流转已在原型中模拟。'); }
  if (event.target.closest('[data-close-drawer]')) document.querySelector('#drawer').hidden = true;
});

document.querySelector('#loginBtn').addEventListener('click', () => {
  document.querySelector('#loginView').hidden = true;
  document.querySelector('#appView').hidden = false;
  navigate('dashboard');
});
document.querySelector('#logoutBtn').addEventListener('click', () => {
  document.querySelector('#appView').hidden = true;
  document.querySelector('#loginView').hidden = false;
});
document.querySelector('#roleSelect').addEventListener('change', e => toast(`已切换为${e.target.value}视角，菜单权限在原型中完整展示。`));

renderMenu();
