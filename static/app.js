const state = {
  courses: [],
  requirements: {},
  completed: new Set(),
  currentAcademicYear: 1,
  currentSemester: 'spring',
  teamModules: [],
  hasCycle: false,
  lastRecommendation: null,
  lastRoadmap: null,
};

const TEAM_MEMBER_NAME_BY_INDEX = {
  '1': '김유빈',
  '2': '김도훈',
  '3': '신한서',
  '4': '신호진',
};

function resolveTeamMemberLabel(rawName) {
  const member = String(rawName ?? '').trim();
  const match = member.match(/^팀원\s*([1-4])$/);
  if (match && TEAM_MEMBER_NAME_BY_INDEX[match[1]]) {
    return TEAM_MEMBER_NAME_BY_INDEX[match[1]];
  }
  return member || '미지정';
}

const $ = (id) => document.getElementById(id);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, (ch) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;',
  })[ch]);
}

function showToast(message, tone = 'ok') {
  const stack = $('toastStack');
  if (!stack) return;
  const node = document.createElement('div');
  node.className = `toast ${tone}`;
  node.textContent = String(message || '');
  stack.appendChild(node);
  const limit = 3;
  while (stack.children.length > limit) {
    stack.firstElementChild?.remove();
  }
  window.setTimeout(() => node.remove(), 2500);
}

function downloadTextFile(filename, content, mimeType = 'text/plain;charset=utf-8') {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function timestampForFilename() {
  const now = new Date();
  const pad = (value) => String(value).padStart(2, '0');
  return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}`;
}

async function api(path, payload = null) {
  const options = payload === null
    ? {}
    : {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      };
  const response = await fetch(path, options);
  const json = await response.json();
  if (!response.ok || !json.ok) {
    throw new Error(json.error || '요청 처리 중 오류가 발생했습니다.');
  }
  return json.data;
}

function selectedCompleted() {
  return $$('#completedBox input[type="checkbox"]:checked').map((input) => input.value);
}

function currentSemesterKo() {
  return state.currentSemester === 'spring' ? '1학기' : '2학기';
}

function seasonKo(season) {
  return season === 'spring' ? '1학기' : '2학기';
}

function applyCurrentTermToPanels() {
  $('recommendSeason').value = state.currentSemester;
}

function applyRoadmapDefaultsFromCurrentTerm() {
  const semesterIndex = (state.currentAcademicYear - 1) * 2 + (state.currentSemester === 'fall' ? 1 : 0);
  const remaining = 8 - semesterIndex;
  const roadmapInput = $('roadmapSemesters');
  if (!roadmapInput) return;
  const min = Number(roadmapInput.min || 1);
  const max = Number(roadmapInput.max || 8);
  const safe = Math.max(min, Math.min(max, remaining));
  roadmapInput.value = String(safe);
}

function syncCurrentTermFromUI() {
  const year = Number($('currentYear').value || state.currentAcademicYear);
  state.currentAcademicYear = Number.isFinite(year) ? Math.max(1, Math.min(4, Math.round(year))) : 1;
  state.currentSemester = $('currentSemester').value === 'fall' ? 'fall' : 'spring';
  $('currentYear').value = String(state.currentAcademicYear);
  $('currentSemester').value = state.currentSemester;
  applyCurrentTermToPanels();
  applyRoadmapDefaultsFromCurrentTerm();
  applyDefaultCompletedForCurrentTerm();
  renderCompletedBox();
  renderStatusCards();
  syncCompletedFromUI();
}

function termIndex(year, semester) {
  const normalizedYear = Math.max(1, Math.min(4, Number(year) || 1));
  return (normalizedYear - 1) * 2 + (semester === 'fall' ? 1 : 0);
}

function courseTermIndexes(course) {
  const base = (Math.max(1, Math.min(4, Number(course.year_level) || 1)) - 1) * 2;
  const offerings = Array.isArray(course.offerings) ? course.offerings : [];
  const indexes = [];
  if (offerings.includes('spring') || offerings.includes('both') || offerings.length === 0) {
    indexes.push(base);
  }
  if (offerings.includes('fall') || offerings.includes('both')) {
    indexes.push(base + 1);
  }
  return indexes;
}

function completedCourseSetBeforeCurrentTerm(year, semester) {
  const currentIndex = termIndex(year, semester);
  return new Set(
    state.courses
      .filter((course) => courseTermIndexes(course).some((idx) => idx < currentIndex))
      .map((course) => course.course_id)
  );
}

function applyDefaultCompletedForCurrentTerm() {
  state.completed = completedCourseSetBeforeCurrentTerm(state.currentAcademicYear, state.currentSemester);
}

function syncCompletedFromUI() {
  state.completed = new Set(selectedCompleted());
  $('completedSummary').value = `이수 과목 ${state.completed.size}개 기준(${state.currentAcademicYear}학년 ${currentSemesterKo()})`;
}

function roadmapSemesterLabel(startYear, startSemester, semesterNo) {
  const normalized = Number(semesterNo || 1);
  const offset = startSemester === 'fall' ? 1 : 0;
  const academicYear = Math.max(1, Number(startYear) || 1) + Math.floor((offset + normalized - 1) / 2);
  const season = (offset + normalized - 1) % 2 === 0 ? '1학기' : '2학기';
  return { academicYear, season };
}

function renderRoadmapText(data, startYear, startSemester) {
  const title = escapeHtml(data.message || '로드맵 생성 결과');
  const targetCourses = (data.target_courses || [])
    .map((course) => `${escapeHtml(course.course_name)}(${escapeHtml(course.course_id)})`)
    .join(', ');
  const semesterLines = (data.semesters || []).map((sem) => {
    const semesterNo = Number(sem.semester_no || 0);
    const label = roadmapSemesterLabel(startYear, startSemester, semesterNo);
    const credit = Number(sem.credit_sum || 0);
    const courses = Array.isArray(sem.courses) ? sem.courses : [];
    const courseLines = courses.length > 0
      ? courses.map((course) => `- ${escapeHtml(course.course_name)} | ${escapeHtml(course.course_id)} | ${escapeHtml(course.category)} | ${course.credit}학점 | 난이도 ${course.difficulty}`).join('\n')
      : '- 배치 가능한 목표 과목 없음';
    return `\n[${label.academicYear}학년 ${label.season}(${semesterNo}번째 학기) / ${credit}학점]\n${courseLines}`;
  });
  return [
    title,
    `목표 과목: ${targetCourses || '없음'}`,
    ...semesterLines,
  ].join('\n');
}

function seasonLabelFromOfferings(course) {
  const seasons = Array.isArray(course.offerings) ? course.offerings : [];
  const hasSpring = seasons.includes('spring');
  const hasFall = seasons.includes('fall');
  if (seasons.includes('both') || (hasSpring && hasFall)) {
    return '1,2학기';
  }
  if (hasSpring) return '1학기';
  if (hasFall) return '2학기';
  return '미정';
}

function courseCard(course, score = null) {
  const prereq = course.prerequisite_names?.length ? course.prerequisite_names.join(', ') : '없음';
  const scoreBadge = score === null ? '' : `<span class="pill yellow">점수 ${score}</span>`;
  return `
    <article class="course-card">
      <h3>${escapeHtml(course.course_name)} <span class="pill">${escapeHtml(course.course_id)}</span></h3>
      <p>${escapeHtml(course.category)} · ${course.credit}학점 · 난이도 ${course.difficulty} · 권장 ${course.year_level}학년</p>
      <p>선수과목: ${escapeHtml(prereq)}</p>
      <div class="meta">
        <span class="pill">개설: ${escapeHtml(course.offerings_ko || '-')}</span>
        ${scoreBadge}
      </div>
    </article>`;
}

function courseTable(courses) {
  if (!courses || courses.length === 0) {
    return '<div class="message">해당 과목이 없습니다.</div>';
  }
  return `
    <div class="table-wrap">
      <table class="simple-table">
        <thead><tr><th>코드</th><th>과목명</th><th>분류</th><th>학점</th><th>난이도</th></tr></thead>
        <tbody>
          ${courses.map((course) => `
            <tr>
              <td>${escapeHtml(course.course_id)}</td>
              <td>${escapeHtml(course.course_name)}</td>
              <td>${escapeHtml(course.category)}</td>
              <td>${course.credit}</td>
              <td>${course.difficulty}</td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>`;
}

function courseStatusTable(courses, completedIds = []) {
  if (!courses || courses.length === 0) {
    return '<div class="message">필요한 선수과목이 없습니다.</div>';
  }
  const completedSet = new Set(completedIds);
  return `
    <div class="table-wrap">
      <table class="simple-table">
        <thead><tr><th>코드</th><th>과목명</th><th>분류</th><th>이수 상태</th></tr></thead>
        <tbody>
          ${courses.map((course) => {
            const completed = completedSet.has(course.course_id);
            const badge = completed
              ? '<span class="pill green">이수 완료</span>'
              : '<span class="pill red">미이수</span>';
            return `
              <tr>
                <td>${escapeHtml(course.course_id)}</td>
                <td>${escapeHtml(course.course_name)}</td>
                <td>${escapeHtml(course.category)}</td>
                <td>${badge}</td>
              </tr>`;
          }).join('')}
        </tbody>
      </table>
    </div>`;
}

function prerequisiteAvailabilityView(data) {
  const availability = data.availability || {};
  const code = availability.code || (data.is_available_now ? 'available' : 'missing_prerequisite');
  const messageClass = code === 'available' ? 'ok' : code === 'already_completed' ? 'warn' : 'no';
  const pillClass = code === 'available' ? 'green' : code === 'already_completed' ? 'yellow' : 'red';
  const title = availability.title || (data.is_available_now ? '현재 수강 가능' : '현재 수강 불가');
  const message = availability.message || '선택한 과목의 수강 가능 여부를 확인했습니다.';
  const completedLabel = data.is_already_completed ? '이미 이수함' : '아직 이수하지 않음';
  const completedPill = data.is_already_completed
    ? '<span class="pill yellow">수강 대상 제외</span>'
    : '<span class="pill green">신규 수강 가능 대상</span>';
  const missingNames = (data.missing_direct || []).map((course) => course.course_name).join(', ');
  const prereqLabel = data.direct_prerequisites_satisfied
    ? '직접 선수과목 충족'
    : `${missingNames || '필수 선수과목'} 미이수`;
  const prereqPill = data.direct_prerequisites_satisfied
    ? '<span class="pill green">충족</span>'
    : '<span class="pill red">미충족</span>';
  return `
    <div class="message ${messageClass} prerequisite-status">
      <h3>
        ${escapeHtml(data.target.course_name)} (${escapeHtml(data.target.course_id)})
        <span class="pill ${pillClass}">${escapeHtml(title)}</span>
      </h3>
      <p>${escapeHtml(message)}</p>
      <div class="availability-grid">
        <div class="availability-item">
          <span>이수 여부</span>
          <strong>${escapeHtml(completedLabel)}</strong>
          ${completedPill}
        </div>
        <div class="availability-item">
          <span>선수과목 상태</span>
          <strong>${escapeHtml(prereqLabel)}</strong>
          ${prereqPill}
        </div>
      </div>
      <p class="algorithm-note">${escapeHtml(data.algorithm_note)}</p>
    </div>`;
}

function renderCourseCards(courses, containerId) {
  const target = $(containerId);
  if (!courses || courses.length === 0) {
    target.innerHTML = '<div class="message">검색 결과가 없습니다.</div>';
    return;
  }
  target.innerHTML = courses.map((course) => courseCard(course)).join('');
}

function renderCompletedBox() {
  const groups = new Map();
  for (const course of state.courses) {
    const key = `${course.year_level}학년 · ${seasonLabelFromOfferings(course)}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(course);
  }

  const orderSeasons = ['1학기', '2학기', '1,2학기', '미정'];
  const orderedKeys = [...groups.keys()].sort((a, b) => {
    const [aYear, aSemester] = a.split(' · ');
    const [bYear, bSemester] = b.split(' · ');
    const yearDiff = Number(aYear.replace('학년', '')) - Number(bYear.replace('학년', ''));
    if (yearDiff !== 0) {
      return yearDiff;
    }
    return orderSeasons.indexOf(aSemester) - orderSeasons.indexOf(bSemester);
  });

  let html = '';
  for (const key of orderedKeys) {
    const [yearLabel, semesterLabel] = key.split(' · ');
    const courses = groups.get(key) || [];
    html += `<div class="section-title section-subtitle">${escapeHtml(`${yearLabel} ${semesterLabel}`)}</div>`;
    html += courses.map((course) => {
      const checked = state.completed.has(course.course_id) ? 'checked' : '';
      return `
        <label>
          <input type="checkbox" value="${escapeHtml(course.course_id)}" ${checked} />
          <span class="completed-course">
            <strong class="completed-course-name">${escapeHtml(course.course_name)}</strong>
            <small class="completed-course-meta">${escapeHtml(course.course_id)} · ${escapeHtml(course.category)} · ${course.credit}학점</small>
          </span>
        </label>`;
    }).join('');
  }
  $('completedBox').innerHTML = html;
  $$('#completedBox input[type="checkbox"]').forEach((input) => input.addEventListener('change', () => {
    syncCompletedFromUI();
    renderStatusCards();
  }));
  syncCompletedFromUI();
}

function renderCourseSelect() {
  const options = state.courses.map((course) => `<option value="${escapeHtml(course.course_id)}">${escapeHtml(course.course_name)} (${escapeHtml(course.course_id)})</option>`).join('');
  $('targetCourse').innerHTML = options;
  if (state.courses.some((course) => course.course_id === 'CSE406')) {
    $('targetCourse').value = 'CSE406';
  }
}

function renderTeamModules() {
  const modules = state.teamModules.map((mod) => ({
    ...mod,
    member: resolveTeamMemberLabel(mod.member),
  }));
  $('teamModules').innerHTML = modules.map((mod) => `
    <div class="team-row">
      <strong>${escapeHtml(mod.member)}</strong>
      <div><b>역할</b><br>${escapeHtml(mod.role)}</div>
      <div><b>자료구조 2개</b><br>${mod.data_structures.map(escapeHtml).join(' · ')}</div>
      <div><b>알고리즘 2개</b><br>${mod.algorithms.map(escapeHtml).join(' · ')}</div>
    </div>`).join('');
}

function getRecommendationParams() {
  return {
    completed: selectedCompleted(),
    season: $('recommendSeason').value,
    current_year: state.currentAcademicYear,
    max_credit: Number($('recommendCredit').value || 18),
  };
}

async function getRecommendationData() {
  return api('/api/recommend', getRecommendationParams());
}

async function renderStatusCards() {
  try {
    const rec = await getRecommendationData();
    const earnedTotal = rec.earned['총전공학점'] || 0;
    const requiredTotal = state.requirements['총전공학점'] || 0;
    const summaryRows = [
      ['기초교양', '기초교양', state.requirements['기초교양'] || 0],
      ['융합교양', '융합교양', state.requirements['융합교양'] || 0],
      ['계열교양', '계열교양', state.requirements['계열교양'] || 0],
      ['필수전공', '필수전공', state.requirements['필수전공'] || state.requirements['전공필수'] || 0],
      ['선택전공', '선택전공', state.requirements['선택전공'] || state.requirements['전공선택'] || 0],
    ];
    const deficitCards = summaryRows
      .filter(([, , required]) => required > 0)
      .map(([, label, required]) => {
        const have = rec.earned[label] || 0;
        return `<div class="stat-card"><span>${label} 부족</span><strong>${Math.max(required - have, 0)}학점</strong></div>`;
      }).join('');
    $('statusCards').innerHTML = `
      <div class="stat-card"><span>현재 기준 학기</span><strong>${state.currentAcademicYear}학년 ${currentSemesterKo()}</strong></div>
      <div class="stat-card"><span>이수 과목</span><strong>${selectedCompleted().length}개</strong></div>
      <div class="stat-card"><span>총 전공학점</span><strong>${earnedTotal}/${requiredTotal}</strong></div>
      ${deficitCards}
    `;
  } catch (error) {
    $('statusCards').innerHTML = `<div class="message no">상태 계산 오류: ${escapeHtml(error.message)}</div>`;
  }
}

function runWithBusy(button, label, task, tone = 'ok') {
  return (async () => {
    if (!button) {
      return task();
    }
    const original = button.innerHTML;
    let failed = false;
    button.classList.add('is-busy');
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    if (label) {
      button.textContent = label;
    }
    try {
      return await task();
    } catch (error) {
      failed = true;
      throw error;
    } finally {
      button.classList.remove('is-busy');
      button.disabled = false;
      button.removeAttribute('aria-busy');
      button.innerHTML = original;
      const safeTone = failed ? 'error' : tone;
      showToast(label ? `${label}${failed ? ' 실패' : ' 완료'}` : '요청 완료', safeTone);
    }
  })();
}

async function runSearch() {
  const prefixValue = $('prefixInput').value;
  const keywordValue = $('keywordInput').value;
  return runWithBusy($('searchBtn'), '검색 중...', async () => {
    $('autocompleteResult').innerHTML = '<div class="message">검색 중...</div>';
    $('keywordResult').innerHTML = '<div class="message">검색 중...</div>';
    try {
      const data = await api('/api/search', {
        prefix: prefixValue,
        keyword: keywordValue,
      });
      renderCourseCards(data.autocomplete, 'autocompleteResult');
      renderCourseCards(data.keyword_search, 'keywordResult');
      return data;
    } catch (error) {
      $('autocompleteResult').innerHTML = `<div class="message no">${escapeHtml(error.message)}</div>`;
      $('keywordResult').innerHTML = `<div class="message no">${escapeHtml(error.message)}</div>`;
      throw error;
    }
  }, 'ok');
}

function clearSearchInputs() {
  $('prefixInput').value = '';
  $('keywordInput').value = '';
  $('autocompleteResult').innerHTML = '<div class="message">입력 후 검색을 실행하세요.</div>';
  $('keywordResult').innerHTML = '<div class="message">입력 후 검색을 실행하세요.</div>';
}

async function runPrerequisite() {
  return runWithBusy($('prereqBtn'), '검증 중...', async () => {
    $('prereqResult').innerHTML = '<div class="message">검증 중...</div>';
    try {
      const data = await api('/api/prerequisite', {
        completed: selectedCompleted(),
        course_id: $('targetCourse').value,
      });
      $('prereqResult').innerHTML = `
        ${prerequisiteAvailabilityView(data)}
        <div class="cols">
          <div class="mini-list">
            <h3>직접 선수과목 충족 현황</h3>
            ${courseStatusTable(data.direct_prerequisites, data.completed)}
          </div>
          <div class="mini-list">
            <h3>미이수 직간접 선수과목</h3>
            ${courseTable(data.missing_all)}
          </div>
        </div>
          <div class="mini-list spaced-block">
          <h3>위상정렬 기반 수강 순서 (전공 과목만)</h3>
          <p>${data.topological_order.map((course) => escapeHtml(course.course_name)).join(' → ')}</p>
        </div>`;
      return data;
    } catch (error) {
      $('prereqResult').innerHTML = `<div class="message no">${escapeHtml(error.message)}</div>`;
      throw error;
    }
  }, 'ok');
}

function scoreTable(items) {
  if (!items || items.length === 0) {
    return '<div class="message">추천 과목이 없습니다.</div>';
  }
  return items.map((item) => courseCard(item.course, item.score)).join('');
}

async function runRecommend() {
  return runWithBusy($('recommendBtn'), '추천 계산 중...', async () => {
    $('recommendResult').innerHTML = '<div class="message">추천 계산 중...</div>';
    const data = await getRecommendationData();
    state.lastRecommendation = data;
    await renderStatusCards();
    $('recommendResult').innerHTML = `
      <div class="message ok">
        <h3>${escapeHtml(data.season_ko)} 추천 결과</h3>
        <p>${escapeHtml(data.algorithm_note)}</p>
      </div>
      <div class="cols">
        <div class="mini-list">
          <h3>졸업요건 부족 학점</h3>
          <ul>
            <li>기초교양: ${data.deficits['기초교양'] || 0}학점</li>
            <li>융합교양: ${data.deficits['융합교양'] || 0}학점</li>
            <li>계열교양: ${data.deficits['계열교양'] || 0}학점</li>
            <li>필수전공: ${data.deficits['필수전공'] || data.deficits['전공필수'] || 0}학점</li>
            <li>선택전공: ${data.deficits['선택전공'] || data.deficits['전공선택'] || 0}학점</li>
            <li>총전공학점: ${data.deficits['총전공학점'] || 0}학점</li>
          </ul>
        </div>
        <div class="mini-list">
          <h3>바로 수강 가능한 과목</h3>
          ${courseTable(data.available)}
        </div>
      </div>
      <div class="result-grid">
        <div class="output-box">
          <div class="section-title">Greedy + Heap 추천 TOP</div>
          ${scoreTable(data.greedy)}
        </div>
        <div class="output-box">
          <div class="section-title">0/1 Knapsack DP 추천 조합 (${data.dp_credit_sum}학점 / 점수 ${data.dp_score_sum})</div>
          ${scoreTable(data.dp)}
        </div>
      </div>`;
    return data;
  }, 'ok');
}

async function runRoadmap() {
  const startYear = Number($('currentYear').value || state.currentAcademicYear);
  const startSemester = $('currentSemester').value === 'fall' ? 'fall' : 'spring';
  state.currentAcademicYear = Number.isFinite(startYear) ? Math.max(1, Math.min(4, Math.round(startYear))) : state.currentAcademicYear;
  state.currentAcademicYear = Math.max(1, Number(state.currentAcademicYear));
  state.currentSemester = startSemester;
  $('currentYear').value = String(state.currentAcademicYear);
  $('currentSemester').value = startSemester;
  applyCurrentTermToPanels();
  syncCompletedFromUI();

  return runWithBusy($('roadmapBtn'), '로드맵 생성 중...', async () => {
    $('roadmapResult').innerHTML = '<div class="message">로드맵 생성 중...</div>';
    const data = await api('/api/roadmap', {
      completed: selectedCompleted(),
      start_year: Number(state.currentAcademicYear),
      start_season: startSemester,
      max_semesters: Number($('roadmapSemesters').value || 4),
      max_credit: Number($('roadmapCredit').value || 18),
    });
    state.lastRoadmap = data;
    const roadmapStartYear = Number(state.currentAcademicYear);
    const roadmapStartSeason = data.start_season || startSemester;
    const semesters = data.semesters.map((sem) => {
      const label = roadmapSemesterLabel(roadmapStartYear, roadmapStartSeason, sem.semester_no);
      return `<article class="semester">
        <h3>${escapeHtml(`${label.academicYear}학년 ${label.season}`)} · ${sem.credit_sum}학점</h3>
        ${sem.courses.length ? courseTable(sem.courses) : '<div class="message">배치 가능한 목표 과목 없음</div>'}
      </article>`;
    }).join('');
    $('roadmapResult').innerHTML = `
      <div class="message ${data.feasible ? 'ok' : 'no'}">
        <h3>${escapeHtml(data.message)}</h3>
        <p>${escapeHtml(data.algorithm_note)}</p>
      </div>
      <div class="mini-list">
        <h3>목표 과목 ${data.target_courses.length}개</h3>
        <p>${data.target_courses.map((course) => `${escapeHtml(course.course_name)}(${escapeHtml(course.course_id)})`).join(', ')}</p>
      </div>
      <div class="roadmap">${semesters || '<div class="message">로드맵이 생성되지 않았습니다.</div>'}</div>
      <details class="spaced-block">
        <summary>텍스트 결과 보기</summary>
        <pre>${escapeHtml(renderRoadmapText(data, roadmapStartYear, roadmapStartSeason))}</pre>
      </details>`;
    return data;
  }, 'ok');
}

function exportRecommendationJson() {
  if (!state.lastRecommendation) {
    showToast('먼저 추천을 실행하세요.', 'warn');
    return;
  }
  const payload = {
    exported_at: new Date().toISOString(),
    current_year: state.currentAcademicYear,
    current_semester: state.currentSemester,
    completed: selectedCompleted(),
    recommendation: state.lastRecommendation,
  };
  downloadTextFile(
    `GradRoad_recommendation_${timestampForFilename()}.json`,
    JSON.stringify(payload, null, 2),
    'application/json;charset=utf-8'
  );
}

function exportRoadmapText() {
  if (!state.lastRoadmap) {
    showToast('먼저 로드맵을 생성하세요.', 'warn');
    return;
  }
  const startYear = Number(state.lastRoadmap.start_year || state.currentAcademicYear);
  const startSeason = state.lastRoadmap.start_season || state.currentSemester;
  const text = renderRoadmapText(state.lastRoadmap, startYear, startSeason);
  downloadTextFile(`GradRoad_roadmap_${timestampForFilename()}.txt`, text);
}

function exportRoadmapJson() {
  if (!state.lastRoadmap) {
    showToast('먼저 로드맵을 생성하세요.', 'warn');
    return;
  }
  const payload = {
    exported_at: new Date().toISOString(),
    current_year: state.currentAcademicYear,
    current_semester: state.currentSemester,
    completed: selectedCompleted(),
    roadmap: state.lastRoadmap,
  };
  downloadTextFile(
    `GradRoad_roadmap_${timestampForFilename()}.json`,
    JSON.stringify(payload, null, 2),
    'application/json;charset=utf-8'
  );
}

function clearCompletedCourses() {
  state.completed = new Set();
  renderCompletedBox();
  renderStatusCards();
  refreshActiveComputation();
  showToast('이수 과목을 모두 해제했습니다.', 'warn');
}

function setActiveTab(tabName) {
  const tabs = $$('.tab');
  const targetPanel = document.getElementById(`tab-${tabName}`);
  if (!targetPanel) return;
  const nextTab = tabs.find((tab) => tab.dataset.tab === tabName) || null;
  tabs.forEach((btn) => {
    const isActive = btn === nextTab;
    btn.classList.toggle('active', isActive);
    btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
    btn.tabIndex = isActive ? 0 : -1;
  });
  $$('.tab-panel').forEach((panel) => panel.classList.toggle('active', panel.id === `tab-${tabName}`));
}

function initHeroMap() {
  const canvas = $('heroMapCanvas');
  const hero = $('heroCover');
  if (!canvas || !hero) return;

  const ctx = canvas.getContext('2d');
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const pointer = { x: 0.68, y: 0.42, active: false };
  let width = 0;
  let height = 0;
  let animationId = null;

  const heroCourses = state.courses.length
    ? state.courses.filter((course) => Number(course.credit || 0) > 0).slice(0, 18)
    : [
        { course_id: 'CSE106', course_name: '선형대수' },
        { course_id: 'CSE122', course_name: '자료구조' },
        { course_id: 'CSE136', course_name: '알고리즘' },
        { course_id: 'CSE141', course_name: '프로젝트' },
      ];

  const nodes = heroCourses.map((course, index) => {
    const col = index % 6;
    const row = Math.floor(index / 6);
    return {
      label: course.course_id || course.course_name,
      x: 0.42 + col * 0.1,
      y: 0.18 + row * 0.22 + (col % 2) * 0.055,
      phase: index * 0.63,
      radius: index % 5 === 0 ? 18 : 14,
    };
  });

  function resize() {
    const rect = hero.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = Math.max(1, rect.width);
    height = Math.max(1, rect.height);
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function draw(time = 0) {
    ctx.clearRect(0, 0, width, height);
    const t = time * 0.001;
    const points = nodes.map((node) => {
      const driftX = reduceMotion ? 0 : Math.sin(t + node.phase) * 8;
      const driftY = reduceMotion ? 0 : Math.cos(t * 0.8 + node.phase) * 7;
      const px = node.x * width + driftX;
      const py = node.y * height + driftY;
      const dx = px - pointer.x * width;
      const dy = py - pointer.y * height;
      const distance = Math.max(1, Math.hypot(dx, dy));
      const pull = pointer.active ? Math.max(0, 1 - distance / 280) * 16 : 0;
      return {
        ...node,
        px: px + (dx / distance) * pull,
        py: py + (dy / distance) * pull,
      };
    });

    ctx.lineWidth = 1;
    for (let index = 0; index < points.length; index += 1) {
      const current = points[index];
      const next = points[index + 1];
      const lower = points[index + 6];
      [next, lower].filter(Boolean).forEach((target) => {
        ctx.beginPath();
        ctx.moveTo(current.px, current.py);
        ctx.lineTo(target.px, target.py);
        ctx.strokeStyle = 'rgba(100, 210, 255, 0.22)';
        ctx.stroke();
      });
    }

    points.forEach((node, index) => {
      const pulse = reduceMotion ? 0 : Math.sin(t * 1.6 + node.phase) * 2;
      ctx.beginPath();
      ctx.arc(node.px, node.py, node.radius + pulse, 0, Math.PI * 2);
      ctx.fillStyle = index % 3 === 0 ? 'rgba(10, 132, 255, 0.86)' : index % 3 === 1 ? 'rgba(100, 210, 255, 0.82)' : 'rgba(255, 159, 10, 0.84)';
      ctx.fill();
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.56)';
      ctx.stroke();

      ctx.font = '700 11px Pretendard, system-ui, sans-serif';
      ctx.fillStyle = 'rgba(9, 25, 22, 0.92)';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(String(node.label).slice(0, 7), node.px, node.py + 0.5);
    });

  }

  resize();
  draw();
  window.addEventListener('resize', () => {
    resize();
    draw();
  });
  hero.addEventListener('pointermove', (event) => {
    const rect = hero.getBoundingClientRect();
    pointer.x = (event.clientX - rect.left) / rect.width;
    pointer.y = (event.clientY - rect.top) / rect.height;
    pointer.active = true;
  });
  hero.addEventListener('pointerleave', () => {
    pointer.active = false;
  });

  if (!reduceMotion) {
    const loop = (time) => {
      draw(time);
      animationId = window.requestAnimationFrame(loop);
    };
    animationId = window.requestAnimationFrame(loop);
  }
  window.addEventListener('beforeunload', () => {
    if (animationId) window.cancelAnimationFrame(animationId);
  });
}

async function refreshActiveComputation() {
  const activeTab = document.querySelector('.tab.active')?.dataset.tab;
  if (activeTab === 'recommend') {
    await runRecommend();
  }
  if (activeTab === 'roadmap') {
    await runRoadmap();
  }
}

function bindEvents() {
  $$('[data-hero-tab]').forEach((button) => {
    button.addEventListener('click', () => {
      const tabName = button.dataset.heroTab;
      setActiveTab(tabName);
      document.querySelector('.tabs-shell')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      if (tabName === 'roadmap') {
        runRoadmap();
      }
      if (tabName === 'search') {
        runSearch();
      }
    });
  });

  $$('.tab').forEach((button) => {
    button.addEventListener('click', async () => {
      const tabName = button.dataset.tab;
      setActiveTab(tabName);
      if (tabName === 'prerequisite') {
        await runPrerequisite();
      }
      if (tabName === 'search') {
        await runSearch();
      }
      if (tabName === 'recommend') {
        await runRecommend();
      }
      if (tabName === 'roadmap') {
        await runRoadmap();
      }
    });
    button.addEventListener('keydown', (event) => {
      if (!['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(event.key)) {
        return;
      }
      const tabs = $$('.tab');
      const index = tabs.indexOf(button);
      if (index === -1) return;
      let nextIndex = index;
      if (event.key === 'ArrowRight') {
        nextIndex = (index + 1) % tabs.length;
      } else if (event.key === 'ArrowLeft') {
        nextIndex = (index - 1 + tabs.length) % tabs.length;
      } else if (event.key === 'Home') {
        nextIndex = 0;
      } else if (event.key === 'End') {
        nextIndex = tabs.length - 1;
      }
      event.preventDefault();
      setActiveTab(tabs[nextIndex].dataset.tab);
      tabs[nextIndex].focus();
    });
  });

  $('currentYear').addEventListener('change', () => {
    syncCurrentTermFromUI();
    refreshActiveComputation();
  });
  $('currentSemester').addEventListener('change', () => {
    syncCurrentTermFromUI();
    refreshActiveComputation();
  });

  $('searchBtn').addEventListener('click', runSearch);
  $('clearSearchBtn').addEventListener('click', clearSearchInputs);
  $('clearCompletedBtn').addEventListener('click', clearCompletedCourses);
  $('prefixInput').addEventListener('keydown', (event) => {
    if (event.key === 'Enter') runSearch();
  });
  $('keywordInput').addEventListener('keydown', (event) => {
    if (event.key === 'Enter') runSearch();
  });

  $('prereqBtn').addEventListener('click', runPrerequisite);
  $('recommendBtn').addEventListener('click', runRecommend);
  $('recommendExportBtn').addEventListener('click', exportRecommendationJson);
  $('roadmapBtn').addEventListener('click', runRoadmap);
  $('roadmapTextBtn').addEventListener('click', exportRoadmapText);
  $('roadmapJsonBtn').addEventListener('click', exportRoadmapJson);
  $('recommendSeason').addEventListener('change', () => {
    state.currentSemester = $('recommendSeason').value === 'fall' ? 'fall' : 'spring';
    syncCurrentTermFromUI();
    refreshActiveComputation();
  });
  $('recommendCredit').addEventListener('change', () => {
    renderStatusCards();
    if (document.querySelector('.tab.active')?.dataset.tab === 'recommend') {
      runRecommend();
    }
  });
}

async function init() {
  const summary = await api('/api/summary');
  state.courses = summary.courses.sort((a, b) => a.year_level - b.year_level || a.course_id.localeCompare(b.course_id));
  state.requirements = summary.requirements;
  state.completed = new Set();
  state.currentAcademicYear = 1;
  state.currentSemester = 'spring';
  state.teamModules = summary.team_modules;
  state.hasCycle = summary.has_cycle;

  $('currentYear').value = String(state.currentAcademicYear);
  $('currentSemester').value = state.currentSemester;
  $('courseCount').textContent = `${summary.course_count}개`;
  $('cycleState').textContent = summary.has_cycle ? '오류 있음' : '정상';
  initHeroMap();
  renderTeamModules();
  applyCurrentTermToPanels();
  applyRoadmapDefaultsFromCurrentTerm();
  renderCompletedBox();
  renderCourseSelect();
  bindEvents();

  await renderStatusCards();
  await runSearch();
  await runPrerequisite();
  await runRecommend();
}

init().catch((error) => {
  document.body.innerHTML = `<main style="max-width:760px;margin:40px auto;padding:0 1rem"><h1>오류 발생</h1><pre>${escapeHtml(error.stack || error.message)}</pre></main>`;
});
