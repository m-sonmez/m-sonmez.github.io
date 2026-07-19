window.clinicalCharts = window.clinicalCharts || {};
window.endAnimation = function (isPaused = false) {
    if (window.timelineInterval) {
        clearInterval(window.timelineInterval);
        window.timelineInterval = null;
    }
    const appNode = document.querySelector('[x-data="dashboardApp()"]');
    if (appNode) {
        const app = Alpine.$data(appNode);
        app.animStatus = isPaused ? 'paused' : 'idle';
    }
};
window.runTimelineStep = function () {
    const appNode = document.querySelector('[x-data="dashboardApp()"]');
    const app = Alpine.$data(appNode);
    let parts = app.endDate.split('-');
    let currentDate = new Date(parts[0], parts[1] - 1, parts[2]);
    currentDate.setDate(currentDate.getDate() + 1);
    let nextDateStr = currentDate.getFullYear() + '-' + String(currentDate.getMonth() + 1).padStart(2, '0') + '-' + String(currentDate.getDate()).padStart(2, '0');
    if (nextDateStr > app.animTargetDate) {
        window.endAnimation(false);
        return;
    }
    app.endDate = nextDateStr;
    app.updateFilters();
};
window.startAnimation = function (customStart = null, customEnd = null, isResume = false) {
    const appNode = document.querySelector('[x-data="dashboardApp()"]');
    const app = Alpine.$data(appNode);
    window.endAnimation(false);
    let initialStart = customStart || app.startDate || app.firstD;
    let targetDate = customEnd || app.endDate || app.lastD;
    if (initialStart < app.firstD) initialStart = app.firstD;
    let todayStr = new Date().toISOString().split('T')[0];
    let absoluteLimit = app.lastD < todayStr ? app.lastD : todayStr;
    if (targetDate > absoluteLimit) targetDate = absoluteLimit;
    if (initialStart > targetDate) {
        console.error('❌ Hata: Başlangıç tarihi, hedef tarihinden büyük olamaz!');
        app.animStatus = 'idle';
        return;
    }
    app.animTargetDate = targetDate;
    app.animStatus = 'playing';
    if (!isResume) {
        app.startDate = initialStart;
        app.endDate = initialStart;
    } else {
        app.endDate = customStart;
    }
    app.datePreset = 'custom';
    app.updateFilters();
    const intervals = [2000, 1000, 500, 250, 125];
    window.timelineInterval = setInterval(window.runTimelineStep, intervals[app.animSpeedIndex]);
};
window.updateAnimationSpeed = function () {
    const appNode = document.querySelector('[x-data="dashboardApp()"]');
    const app = Alpine.$data(appNode);
    if (app.animStatus === 'playing') {
        if (window.timelineInterval) clearInterval(window.timelineInterval);
        const intervals = [2000, 1000, 500, 250, 125];
        window.timelineInterval = setInterval(window.runTimelineStep, intervals[app.animSpeedIndex]);
    }
};
export default function registerDashboard(Alpine) {
    Alpine.data('dashboardApp', () => ({
        flowsheetMode: 'grid',
        corsError: false,
        datePreset: 'all',
        startDate: '',
        endDate: '',
        previousStartDate: null,
        previousEndDate: null,
        firstD: '',
        lastD: '',
        dateFiltersOpen: true,
        calendarYear: null,
        calendarMonth: null,
        selectedCalendarDayStr: null,
        showOnlyOutOfBoundsTests: false,
        hideSpecialTests: true,
        user: {},
        hospitals: [],
        medications: [],
        medicationChanges: [],
        medicationLogs: [],
        pressures: [],
        weights: [],
        tests: [],
        testItems: [],
        metrics: { avgSys: 0, avgDia: 0, currentWeight: 0, startWeight: 0, weightDelta: 0, adherenceRate: 100, outOfBoundsCount: 0, outOfBoundsList: [], latestInr: null, latestHgb: null },
        flowsheetDays: [],
        allFlowsheetMeds: [],
        uniqueMeds: [],
        tooltip: { show: false, x: 0, y: 0, med: '', date: '', count: 0, times: [] },
        selectedTestId: null,
        selectedTestObj: {},
        selectedTestItems: [],
        medTimeline: [],
        detailedMeds: [],
        selectedMed: [],
        onlyActive: true,
        activeTooltip: null,
        activeCellTooltip: null,
        medConversions: {},
        medConfig: {
            Dilatrend: { target: 2.0, color: 'rgb(139, 92, 246)' },
            BelocZOK: { target: 1.0, color: 'rgb(245, 158, 11)' },
            Kapril: { target: 0.0, color: 'rgb(220, 38, 38)' },
            Cordarone: { target: 1.0, color: 'rgb(71, 85, 105)' },
            Tavanic: { target: 1.0, color: 'rgb(16, 185, 129)' },
            Cipro: { target: 2.0, color: 'rgb(56, 189, 248)' },
            Stafine: { target: 3.0, color: 'rgb(236, 72, 153)' },
            Mikostatin: { target: 9.0, color: 'rgb(163, 230, 53)' },
            Warfmadin: { target: 1.0, color: 'rgb(249, 115, 22)' },
            EcopirinPro: { target: 1.0, color: 'rgb(20, 184, 166)' },
            Panto: { target: 1.0, color: 'rgb(79, 70, 229)' },
            Apikobal: { target: 1.0, color: 'rgb(250, 204, 21)' },
            GeralginePlus: { target: 1.0, color: 'rgb(190, 24, 93)' },
            Levopront: { target: 2.0, color: 'rgb(148, 163, 184)' },
            Augmentin: { target: 2.0, color: 'rgb(16, 185, 129)' },
        },
        medColors: {
            EcopirinPro: 'bg-orange-400',
            Warfmadin: 'bg-orange-600',
            Kapril: 'bg-blue-400',
            Dilatrend: 'bg-indigo-500',
            BelocZOK: 'bg-amber-500',
            Cordarone: 'bg-slate-500',
            Augmentin: 'bg-emerald-400',
            Cipro: 'bg-sky-400',
            Tavanic: 'bg-emerald-600',
            Stafine: 'bg-pink-500',
            Mikostatin: 'bg-lime-400',
            GeralginePlus: 'bg-pink-700',
            Panto: 'bg-indigo-600',
            Levopront: 'bg-sky-500',
            Apikobal: 'bg-yellow-400',
        },
        medGroups: {
            'Kan Sulandırıcılar': ['EcopirinPro', 'Warfmadin'],
            'Tansiyon & Kalp': ['Kapril', 'Dilatrend', 'BelocZOK', 'Cordarone'],
            'Antibiyotik / Antifungal': ['Augmentin', 'Cipro', 'Tavanic', 'Stafine', 'Mikostatin'],
            'Ağrı Kesici': ['GeralginePlus'],
            'Mide Koruması': ['Panto'],
            'Solunum / Öksürük': ['Levopront'],
            'Vitamin / Takviye': ['Apikobal'],
        },
        bpViewMode: 'trend',
        sections: {
            summary: true,
            charts: true,
            logs: true,
            prescriptions: true,
            flowsheet: false,
            calendar: true,
            clinicalReport: false,
            labTrends: true,
            labFindings: true,
            reports: false,
        },
        animStatus: 'idle',
        animScope: 'all',
        animTargetDate: null,
        animSpeedIndex: 2,
        get animSpeedLabel() {
            return ['x1/2', 'x1', 'x2', 'x4', 'x8'][this.animSpeedIndex];
        },
        isAtTop: true,
        toolbarOpen: true,
        handleScroll() {
            let currentAtTop = window.scrollY < 10;
            if (this.isAtTop !== currentAtTop) {
                this.isAtTop = currentAtTop;
            }
        },
        toggleAnimation() {
            if (this.animStatus === 'playing') {
                window.endAnimation(true);
            } else if (this.animStatus === 'paused') {
                this.animStatus = 'playing';
                window.startAnimation(this.endDate, this.animTargetDate, true);
            } else {
                this.animStatus = 'playing';
                this.onlyActive = false;
                this.toolbarOpen = true;
                let start = this.animScope === 'period' ? this.startDate : this.firstD;
                let end = this.animScope === 'period' ? this.endDate : this.lastD;
                if (start > end) start = end;
                this.animTargetDate = end;
                window.startAnimation(start, end, false);
            }
        },
        stopAnimation() {
            window.endAnimation(false);
        },
        get userInitials() {
            if (!this.user.name) return '--';
            let parts = this.user.name.trim().split(/\s+/);
            if (parts.length >= 2) {
                return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
            }
            return this.user.name.substring(0, 2).toUpperCase();
        },
        get activeMeds() {
            return this.medications.filter((m) => {
                if (this.onlyActive) return this.isMedActiveAtEndDate(m.name);
                return this.isMedicationActiveInRange(m.id);
            });
        },
        get passiveMeds() {
            return this.medications.filter((m) => {
                if (this.onlyActive) return !this.isMedActiveAtEndDate(m.name);
                return !this.isMedicationActiveInRange(m.id);
            });
        },
        convertYmdHiToYmd(at) {
            return at.substring(0, 10);
        },
        get filteredMedTimeline() {
            return this.medicationChanges
                .filter((c) => {
                    return this.convertYmdHiToYmd(c.at) >= this.startDate && this.convertYmdHiToYmd(c.at) <= this.endDate;
                })
                .sort((a, b) => new Date(b.at) - new Date(a.at));
        },
        get filteredTimeline() {
            const start = this.startDate;
            const end = this.endDate;
            let dayEvents = this.medTimeline.filter((e) => {
                const eDate = this.convertYmdHiToYmd(e.date);
                const inDateRange = eDate >= start && eDate <= end;
                const matchesSelection = this.selectedMed.length === 0 || this.selectedMed.includes(e.med);
                const matchesActive = !this.onlyActive || this.isMedActiveAtEndDate(e.med);
                return inDateRange && matchesSelection && matchesActive;
            });
            const medsToShow = this.selectedMed.length === 0 ? [...new Set(this.medTimeline.map((e) => e.med))] : this.selectedMed;
            medsToShow.forEach((medName) => {
                if (this.onlyActive && !this.isMedActiveAtEndDate(medName)) return;
                const hasExactStart = dayEvents.some((e) => e.med === medName && this.convertYmdHiToYmd(e.date) === start);
                if (!hasExactStart && !this.isEmergencyMed(medName)) {
                    const lastEventBefore = [...this.medTimeline].filter((e) => e.med === medName && this.convertYmdHiToYmd(e.date) < start).sort((a, b) => b.date.localeCompare(a.date))[0];
                    if (lastEventBefore && lastEventBefore.type !== 'end') {
                        dayEvents.push({ ...lastEventBefore, date: lastEventBefore.date, msg: lastEventBefore.msg + ' <span class="text-[10px] text-slate-400 italic">(Devam eden doz)</span>' });
                    }
                }
            });
            return dayEvents.sort((a, b) => b.date.localeCompare(a.date));
        },
        populateMedTimeline() {
            const lastKnownDose = {};
            this.medTimeline = [...this.medicationChanges]
                .sort((a, b) => a.at.localeCompare(b.at))
                .map((c) => {
                    const med = this.medications.find((m) => m.id === c.medication_id),
                        name = med ? med.name : 'İlaç',
                        unit = med ? med.unit : 'mg',
                        isEmergency = med && med.is_emergency;
                    let msg = `<b>${name}</b> `;
                    const prev = lastKnownDose[name];
                    if (isEmergency) {
                        msg += `tek seferlik acil durum dozu <b>${c.amount}${unit}</b> olarak uygulandı`;
                    } else {
                        let label = 'dozu';
                        if (c.timespan === 168) label = 'haftalık toplam dozu';
                        else if (c.timespan === 24) label = 'günlük dozu';
                        else if (c.timespan === 12) label = 'günde 2 kez dozu';
                        else if (c.timespan === 8) label = 'günde 3 kez dozu';
                        else if (c.timespan === 72) label = '3 günlük dozu';
                        else label = 'dozu';
                        if (c.type === 'Started') msg += `${label} <b>${c.amount}${unit}</b> olarak başlandı`;
                        else if (c.type === 'Ended') msg += `kullanımı sonlandırıldı`;
                        else if (c.type === 'Paused') msg += `kullanımına ara verildi`;
                        else if (c.type === 'Resumed') msg += `${label} <b>${c.amount}${unit}</b> olarak tekrar başlandı`;
                        else if (c.type === 'Changed') msg += `${label} ${prev ? prev + unit : ''} iken <b>${c.amount}${unit}</b> olarak değiştirildi`;
                    }
                    lastKnownDose[name] = c.amount;
                    return { date: c.at, med: name, type: c.type === 'Ended' || isEmergency ? 'end' : c.type === 'Paused' ? 'pause' : c.type === 'Changed' ? 'change' : 'start', medColor: this.medColors[name] || 'bg-slate-500', msg: msg };
                })
                .reverse();
        },
        get filteredTests() {
            let testsInWindow = this.tests.filter((t) => {
                let d = t.at.substring(0, 10);
                return d >= this.startDate && d <= this.endDate;
            });

            if (this.hideSpecialTests) {
                testsInWindow = testsInWindow.filter((t) => {
                    const title = t.title.toLowerCase();
                    return !title.includes('arter kan gazı') && !title.includes('crossmatch');
                });
            }

            if (this.showOnlyOutOfBoundsTests) {
                testsInWindow = testsInWindow.filter((t) => this.testHasOutOfBounds(t.id));
            }
            testsInWindow.sort((a, b) => new Date(b.at) - new Date(a.at));

            if (testsInWindow.length > 0) {
                return testsInWindow.map((t) => ({ ...t, outOfRange: false }));
            } else {
                let historicalTests = this.tests.filter((t) => t.at.substring(0, 10) <= this.endDate);
                if (this.hideSpecialTests) {
                    historicalTests = historicalTests.filter((t) => {
                        const title = t.title.toLowerCase();
                        return !title.includes('arter kan gazı') && !title.includes('crossmatch');
                    });
                }
                if (this.showOnlyOutOfBoundsTests) {
                    historicalTests = historicalTests.filter((t) => this.testHasOutOfBounds(t.id));
                }
                historicalTests.sort((a, b) => new Date(b.at) - new Date(a.at));
                if (historicalTests.length > 0) {
                    return [{ ...historicalTests[0], outOfRange: true }];
                }
                return [];
            }
        },
        get sortedReports() {
            if (!this.reports || this.reports.length === 0) return [];
            return [...this.reports].sort((a, b) => new Date(b.at) - new Date(a.at));
        },
        toggleHideSpecialTests() {
            const visibleTests = this.filteredTests;
            if (visibleTests.length > 0) {
                this.selectLabSession(visibleTests[0].id);
            } else {
                this.selectedTestId = null;
                this.selectedTestObj = {};
                this.selectedTestItems = [];
            }
        },
        testHasOutOfBounds(testId) {
            let items = this.testItems.filter((ti) => ti.test_id === testId);
            return items.some((item) => this.getLabItemStatus(item) !== 'Normal');
        },
        get calendarMonthName() {
            const months = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'];
            return months[this.calendarMonth] || '';
        },
        canGoPrevMonth() {
            if (!this.firstD) return true;
            let firstParts = this.firstD.split('-');
            let firstYear = parseInt(firstParts[0]);
            let firstMonth = parseInt(firstParts[1]) - 1;
            let targetMonth = this.calendarMonth === 0 ? 11 : this.calendarMonth - 1;
            let targetYear = this.calendarMonth === 0 ? this.calendarYear - 1 : this.calendarYear;
            return targetYear > firstYear || (targetYear === firstYear && targetMonth >= firstMonth);
        },
        canGoNextMonth() {
            if (!this.lastD) return true;
            let lastParts = this.lastD.split('-');
            let lastYear = parseInt(lastParts[0]);
            let lastMonth = parseInt(lastParts[1]) - 1;
            let targetMonth = this.calendarMonth === 11 ? 0 : this.calendarMonth + 1;
            let targetYear = this.calendarMonth === 11 ? this.calendarYear + 1 : this.calendarYear;
            return targetYear < lastYear || (targetYear === lastYear && targetMonth <= lastMonth);
        },
        prevCalendarMonth() {
            let firstParts = this.firstD.split('-');
            let firstYear = parseInt(firstParts[0]);
            let firstMonth = parseInt(firstParts[1]) - 1;
            let targetMonth = this.calendarMonth === 0 ? 11 : this.calendarMonth - 1;
            let targetYear = this.calendarMonth === 0 ? this.calendarYear - 1 : this.calendarYear;
            if (targetYear > firstYear || (targetYear === firstYear && targetMonth >= firstMonth)) {
                this.calendarMonth = targetMonth;
                this.calendarYear = targetYear;
            }
        },
        nextCalendarMonth() {
            let lastParts = this.lastD.split('-');
            let lastYear = parseInt(lastParts[0]);
            let lastMonth = parseInt(lastParts[1]) - 1;
            let targetMonth = this.calendarMonth === 11 ? 0 : this.calendarMonth + 1;
            let targetYear = this.calendarMonth === 11 ? this.calendarYear + 1 : this.calendarYear;
            if (targetYear < lastYear || (targetYear === lastYear && targetMonth <= lastMonth)) {
                this.calendarMonth = targetMonth;
                this.calendarYear = targetYear;
            }
        },
        getMedLogsForDate(dateStr) {
            return this.medicationLogs.filter((l) => l.at.substring(0, 10) === dateStr);
        },
        get calendarDays() {
            let year = this.calendarYear;
            let month = this.calendarMonth;
            if (year === null || month === null) return [];
            let firstDayDate = new Date(year, month, 1);
            let firstDayOfWeek = firstDayDate.getDay();
            let startOffset = firstDayOfWeek === 0 ? 6 : firstDayOfWeek - 1;
            let totalDaysInMonth = new Date(year, month + 1, 0).getDate();
            let prevMonthIndex = month === 0 ? 11 : month - 1;
            let prevYear = month === 0 ? year - 1 : year;
            let totalDaysInPrevMonth = new Date(prevYear, prevMonthIndex + 1, 0).getDate();
            let days = [];
            for (let i = startOffset - 1; i >= 0; i--) {
                let dayNum = totalDaysInPrevMonth - i;
                let mStr = String(prevMonthIndex + 1).padStart(2, '0');
                let dStr = String(dayNum).padStart(2, '0');
                let fullDate = `${prevYear}-${mStr}-${dStr}`;
                days.push({ dayNum: dayNum, dateStr: fullDate, isCurrentMonth: false });
            }
            for (let i = 1; i <= totalDaysInMonth; i++) {
                let mStr = String(month + 1).padStart(2, '0');
                let dStr = String(i).padStart(2, '0');
                let fullDate = `${year}-${mStr}-${dStr}`;
                days.push({ dayNum: i, dateStr: fullDate, isCurrentMonth: true });
            }
            let remainingCells = 42 - days.length;
            let nextMonthIndex = month === 11 ? 0 : month + 1;
            let nextYear = month === 11 ? year + 1 : year;
            for (let i = 1; i <= remainingCells; i++) {
                let mStr = String(nextMonthIndex + 1).padStart(2, '0');
                let dStr = String(i).padStart(2, '0');
                let fullDate = `${nextYear}-${mStr}-${dStr}`;
                days.push({ dayNum: i, dateStr: fullDate, isCurrentMonth: false });
            }
            return days;
        },
        selectCalendarDay(dateStr) {
            if (dateStr >= this.firstD && dateStr <= this.lastD) {
                this.selectedCalendarDayStr = dateStr;
            }
        },
        getCalendarDayClass(day) {
            let isSelected = this.selectedCalendarDayStr === day.dateStr;
            let inRange = day.dateStr >= this.startDate && day.dateStr <= this.endDate;
            let isOutOfBounds = day.dateStr < this.firstD || day.dateStr > this.lastD;
            let classes = '';
            if (isOutOfBounds) {
                classes += ' opacity-10 bg-slate-100/50 cursor-not-allowed pointer-events-none';
            } else if (isSelected) {
                classes += ' ring-2 ring-indigo-600 border-indigo-600 bg-indigo-50/20';
            } else if (!day.isCurrentMonth) {
                classes += ' opacity-40 bg-slate-50/50';
            } else if (inRange) {
                classes += ' bg-white border-slate-200/80';
            } else {
                classes += ' bg-slate-50/30 border-slate-100';
            }
            return classes;
        },
        reports: [],
        selectedReportId: null,
        selectedReportObj: {},
        async initDashboard() {
            try {
                await this.loadAllData();
            } catch (e) {
                console.warn('Asenkron JSON yükleme kesintisi, yerleşik verilere dönülüyor:', e);
                this.corsError = true;
                this.loadBackupData();
            }
            this.medications.forEach((m) => (this.medConversions[m.name] = m.base_dose));
            this.determineGlobalDateLimits();
            this.populateMedTimeline();
            this.calculateMetrics();
            this.updateVisibleMeds();
            this.setupFlowsheet();
            let fTests = this.filteredTests;
            if (fTests.length > 0) {
                this.selectLabSession(fTests[0].id);
            } else if (this.tests.length > 0) {
                let sorted = [...this.tests].sort((a, b) => new Date(b.at) - new Date(a.at));
                this.selectLabSession(sorted[0].id);
            }
            if (this.reports.length > 0) {
                const sortedReports = [...this.reports].sort((a, b) => new Date(b.at) - new Date(a.at));
                if (this.sortedReports.length > 0) {
                    this.selectReport(this.sortedReports[0].protocol_no || this.sortedReports[0].at);
                }
            }
            if (this.endDate) {
                let parts = this.endDate.split('-');
                this.calendarYear = parseInt(parts[0]);
                this.calendarMonth = parseInt(parts[1]) - 1;
                this.selectedCalendarDayStr = this.endDate;
            } else {
                let today = new Date();
                this.calendarYear = today.getFullYear();
                this.calendarMonth = today.getMonth();
                this.selectedCalendarDayStr = today.toISOString().split('T')[0];
            }
            this.$nextTick(() => {
                this.renderMainCharts();
                this.renderLabTrendCharts();
                if (this.flowsheetMode === 'chart') this.renderFocusChart();
            });
        },
        async loadAllData() {
            const [u, h, m, mc, ml, p, w, t, ti, r] = await Promise.all([
                fetch('data/users.json').then((r) => r.json()),
                fetch('data/hospitals.json').then((r) => r.json()),
                fetch('data/medications.json').then((r) => r.json()),
                fetch('data/medication_changes.json').then((r) => r.json()),
                fetch('data/medication_logs.json').then((r) => r.json()),
                fetch('data/pressures.json').then((r) => r.json()),
                fetch('data/weights.json').then((r) => r.json()),
                fetch('data/tests.json').then((r) => r.json()),
                fetch('data/test_items.json').then((r) => r.json()),
                fetch('data/reports.json').then((r) => r.json()),
            ]);
            this.user = u[0] || {};
            this.hospitals = h;
            this.medications = m;
            this.medicationChanges = mc;
            this.medicationLogs = ml;
            this.pressures = p;
            this.weights = w;
            this.tests = t;
            this.testItems = ti;
            this.reports = r;
        },
        selectReport(protocolNo) {
            this.selectedReportId = protocolNo;
            this.selectedReportObj = this.reports.find((r) => (r.protocol_no || r.at) === protocolNo) || {};
        },
        loadBackupData() {
            this.corsError = true;
            this.user = {};
            this.hospitals = [];
            this.medications = [];
            this.medicationChanges = [];
            this.medicationLogs = [];
            this.pressures = [];
            this.weights = [];
            this.tests = [];
            this.testItems = [];
        },
        determineGlobalDateLimits() {
            let pool = [];
            this.pressures.forEach((p) => pool.push(p.at.substring(0, 10)));
            this.weights.forEach((w) => pool.push(w.at.substring(0, 10)));
            this.tests.forEach((t) => pool.push(t.at.substring(0, 10)));
            this.medicationLogs.forEach((ml) => pool.push(ml.at.substring(0, 10)));
            this.medicationChanges.forEach((mc) => pool.push(mc.at.substring(0, 10)));
            this.datePreset = 'all';

            if (pool.length > 0) {
                pool = [...new Set(pool)].sort();
                this.validDatesPool = pool;
                this.firstD = pool[0];
                this.lastD = pool[pool.length - 1];
                let todayStr = new Date().toISOString().split('T')[0];
                this.endDate = this.lastD < todayStr ? this.lastD : todayStr;
                this.applyDatePreset();
            } else {
                this.validDatesPool = [];
                let today = new Date();
                let todayStr = today.toISOString().split('T')[0];
                this.lastD = todayStr;
                let firstDObj = new Date();
                firstDObj.setDate(today.getDate() - 30);
                this.firstD = firstDObj.toISOString().split('T')[0];
                this.endDate = todayStr;
                this.applyDatePreset();
            }
            this.selectedMed = [];
            this.onlyActive = true;
        },
        snapDateToValid(dateStr) {
            if (!this.validDatesPool || this.validDatesPool.length === 0) return dateStr;
            if (this.validDatesPool.includes(dateStr)) return dateStr;
            let targetTime = new Date(dateStr).getTime();
            let closestDate = this.validDatesPool[0];
            let minDiff = Math.abs(new Date(closestDate).getTime() - targetTime);
            for (let i = 1; i < this.validDatesPool.length; i++) {
                let diff = Math.abs(new Date(this.validDatesPool[i]).getTime() - targetTime);
                if (diff < minDiff) {
                    minDiff = diff;
                    closestDate = this.validDatesPool[i];
                }
            }
            return closestDate;
        },
        get latestKilo() {
            const filtered = this.weights.filter((w) => w.at.substring(0, 10) <= this.endDate).sort((a, b) => new Date(b.at) - new Date(a.at));
            return filtered.length > 0 ? { val: filtered[0].weight, date: filtered[0].at.substring(0, 10) } : { val: '-', date: null };
        },
        get previousKilo() {
            const filtered = this.weights.filter((w) => w.at.substring(0, 10) <= this.endDate).sort((a, b) => new Date(b.at) - new Date(a.at));
            if (filtered.length < 2) return '-';
            const current = filtered[0].weight;
            const previous = filtered[1].weight;
            const diff = (current - previous).toFixed(1);
            return `${previous} (${diff >= 0 ? '+' : ''}${diff})`;
        },
        _getBpAvgInRange(daysAgoStart, daysAgoEnd) {
            if (!this.endDate) return null;
            const anchorDate = new Date(this.endDate);
            if (isNaN(anchorDate.getTime())) return null;
            const dStart = new Date(anchorDate);
            dStart.setDate(anchorDate.getDate() - daysAgoStart);
            const dEnd = new Date(anchorDate);
            dEnd.setDate(anchorDate.getDate() - daysAgoEnd);
            const strStart = dStart.toISOString().substring(0, 10);
            const strEnd = dEnd.toISOString().substring(0, 10);
            const targetPressures = this.pressures.filter((p) => {
                const d = p.at.substring(0, 10);
                return d >= strStart && d <= strEnd;
            });
            if (targetPressures.length === 0) return null;
            const s = targetPressures.reduce((a, b) => a + b.sys, 0) / targetPressures.length;
            const d = targetPressures.reduce((a, b) => a + b.dia, 0) / targetPressures.length;
            return { sys: Math.round(s), dia: Math.round(d) };
        },
        get latestBp() {
            const avg = this._getBpAvgInRange(6, 0);
            return avg ? `${avg.sys}/${avg.dia}` : '-';
        },
        get previousBp() {
            const curr = this._getBpAvgInRange(6, 0);
            const prev = this._getBpAvgInRange(13, 7);
            if (!curr || !prev) return '-';
            const diffS = curr.sys - prev.sys;
            const diffD = curr.dia - prev.dia;
            return `${prev.sys}/${prev.dia} (${diffS >= 0 ? '+' : ''}${diffS}/${diffD >= 0 ? '+' : ''}${diffD})`;
        },
        get previousAvgBp() {
            if (this.datePreset === 'all' || !this.startDate || !this.endDate) return '-';
            if (!this.firstD || this.startDate === this.firstD) return '-';
            const startMs = new Date(this.startDate).getTime();
            const endMs = new Date(this.endDate).getTime();
            const diffMs = endMs - startMs;
            if (diffMs < 0) return '-';
            const oneDayMs = 24 * 60 * 60 * 1000;
            const periodDurationDays = Math.round(diffMs / oneDayMs) + 1;
            let prevEndObj = new Date(startMs);
            prevEndObj.setDate(prevEndObj.getDate() - 1);
            let prevStartObj = new Date(startMs);
            prevStartObj.setDate(prevStartObj.getDate() - periodDurationDays);
            const firstDStr = this.firstD;
            let prevStartStr = prevStartObj.toISOString().substring(0, 10);
            const prevEndStr = prevEndObj.toISOString().substring(0, 10);
            if (prevStartStr < firstDStr) {
                prevStartStr = firstDStr;
            }
            if (prevStartStr > prevEndStr) return '-';
            const prevPressures = this.pressures.filter((p) => {
                const d = p.at.substring(0, 10);
                return d >= prevStartStr && d <= prevEndStr;
            });
            if (prevPressures.length === 0) return '-';
            const prevSysAvg = Math.round(prevPressures.reduce((sum, p) => sum + p.sys, 0) / prevPressures.length);
            const prevDiaAvg = Math.round(prevPressures.reduce((sum, p) => sum + p.dia, 0) / prevPressures.length);
            const diffS = this.metrics.avgSys - prevSysAvg;
            const diffD = this.metrics.avgDia - prevDiaAvg;
            return `${prevSysAvg}/${prevDiaAvg} (${diffS >= 0 ? '+' : ''}${diffS}/${diffD >= 0 ? '+' : ''}${diffD})`;
        },
        get latestInr() {
            let tests = [...this.tests].filter((t) => t.at.substring(0, 10) <= this.endDate).sort((a, b) => new Date(b.at) - new Date(a.at));
            for (let t of tests) {
                let item = this.testItems.find((ti) => ti.test_id === t.id && ti.code === 'INR');
                if (item) return { val: parseFloat(item.result).toFixed(2), date: t.at.substring(0, 10) };
            }
            return { val: '-', date: null };
        },
        get previousInr() {
            let tests = [...this.tests].filter((t) => t.at.substring(0, 10) <= this.endDate).sort((a, b) => new Date(b.at) - new Date(a.at));
            let found = [];
            for (let t of tests) {
                let item = this.testItems.find((ti) => ti.test_id === t.id && ti.code === 'INR');
                if (item) found.push(parseFloat(item.result));
                if (found.length === 2) break;
            }
            if (found.length < 2) return '-';
            const diff = (found[0] - found[1]).toFixed(2);
            return `${found[1].toFixed(2)} (${diff >= 0 ? '+' : ''}${diff})`;
        },
        get latestHgb() {
            let tests = [...this.tests].filter((t) => t.at.substring(0, 10) <= this.endDate).sort((a, b) => new Date(b.at) - new Date(a.at));
            for (let t of tests) {
                let item = this.testItems.find((ti) => ti.test_id === t.id && ti.code === 'HGB');
                if (item) return { val: parseFloat(item.result).toFixed(1), date: t.at.substring(0, 10) };
            }
            return { val: '-', date: null };
        },
        get previousHgb() {
            let tests = [...this.tests].filter((t) => t.at.substring(0, 10) <= this.endDate).sort((a, b) => new Date(b.at) - new Date(a.at));
            let found = [];
            for (let t of tests) {
                let item = this.testItems.find((ti) => ti.test_id === t.id && ti.code === 'HGB');
                if (item) found.push(parseFloat(item.result));
                if (found.length === 2) break;
            }
            if (found.length < 2) return '-';
            const diff = (found[0] - found[1]).toFixed(1);
            return `${found[1].toFixed(1)} (${diff >= 0 ? '+' : ''}${diff})`;
        },
        getFilteredPressures() {
            return this.pressures
                .filter((p) => {
                    let d = p.at.substring(0, 10);
                    return d >= this.startDate && d <= this.endDate;
                })
                .sort((a, b) => new Date(b.at) - new Date(a.at));
        },
        getFilteredWeights() {
            return this.weights
                .filter((w) => {
                    let d = w.at.substring(0, 10);
                    return d >= this.startDate && d <= this.endDate;
                })
                .sort((a, b) => new Date(b.at) - new Date(a.at));
        },
        calculateMetrics() {
            let fps = this.getFilteredPressures();
            if (fps.length > 0) {
                this.metrics.avgSys = Math.round(fps.reduce((acc, curr) => acc + curr.sys, 0) / fps.length);
                this.metrics.avgDia = Math.round(fps.reduce((acc, curr) => acc + curr.dia, 0) / fps.length);
            } else {
                this.metrics.avgSys = 0;
                this.metrics.avgDia = 0;
            }
            let inRangeW = this.getFilteredWeights();
            let weightBeforeStart = [...this.weights].filter((w) => w.at.substring(0, 10) < this.startDate).sort((a, b) => new Date(b.at) - new Date(a.at));
            if (inRangeW.length > 0) {
                this.metrics.currentWeight = inRangeW[0].weight;
                let pastWeight = weightBeforeStart.length > 0 ? weightBeforeStart[0].weight : inRangeW[inRangeW.length - 1].weight;
                this.metrics.weightDelta = parseFloat((this.metrics.currentWeight - pastWeight).toFixed(1));
                this.metrics.startWeight = pastWeight;
            } else {
                this.metrics.currentWeight = 0;
                this.metrics.weightDelta = 0;
                this.metrics.startWeight = 0;
            }
            let latestItemPerCode = new Map();
            let activeSessions = [...this.tests].filter((t) => t.at.substring(0, 10) <= this.endDate);
            activeSessions.forEach((t) => {
                let items = this.testItems.filter((item) => item.test_id === t.id);
                items.forEach((item) => {
                    let currentLatest = latestItemPerCode.get(item.code);
                    if (!currentLatest || new Date(t.at) > new Date(currentLatest.rawDate)) {
                        latestItemPerCode.set(item.code, { code: item.code, result: item.result, date: t.at.substring(5, 10), rawDate: t.at, status: this.getLabItemStatus(item) });
                    }
                });
            });
            let outList = [];
            latestItemPerCode.forEach((data) => {
                if (data.status !== 'Normal') {
                    outList.push(data);
                }
            });
            outList.sort((a, b) => (a.date > b.date ? -1 : 1));
            this.metrics.outOfBoundsCount = outList.length;
            this.metrics.outOfBoundsList = outList;
            const getPrescriptionOnDate = (medId, dateStr) => {
                let history = this.medicationChanges.filter((c) => c.medication_id === medId && this.convertYmdHiToYmd(c.at) <= dateStr).sort((a, b) => b.at.localeCompare(a.at));
                if (history.length === 0) return null;
                let last = history[0];
                if (['Ended', 'Paused'].includes(last.type) || last.amount === 0) {
                    return null;
                }
                return last;
            };
            let startMs = new Date(this.startDate + 'T00:00:00');
            let endMs = new Date(this.endDate + 'T23:59:59');
            let daysArray = [];
            let current = new Date(startMs);
            while (current <= endMs) {
                daysArray.push(new Date(current));
                current.setDate(current.getDate() + 1);
            }
            let successUnits = 0;
            let totalUnits = 0;
            let overdoseUnits = 0;
            let underdoseUnits = 0;
            this.medications.forEach((med) => {
                if (med.is_emergency) return;
                daysArray.forEach((dObj) => {
                    let dayStr = dObj.toISOString().split('T')[0];
                    let rx = getPrescriptionOnDate(med.id, dayStr);
                    if (rx && rx.timespan <= 24) {
                        let expected = (24 / rx.timespan) * rx.amount;
                        let logs = this.medicationLogs.filter((l) => l.med.toLowerCase() === med.name.toLowerCase() && l.at.substring(0, 10) === dayStr);
                        let actual = logs.reduce((sum, l) => sum + (parseFloat(l.dose) || 0), 0);
                        totalUnits++;
                        if (actual === expected) {
                            successUnits++;
                        } else if (actual > expected) {
                            overdoseUnits++;
                        } else {
                            underdoseUnits++;
                        }
                    }
                });
                let firstChange = this.medicationChanges.find((c) => c.medication_id === med.id && c.type === 'Started');
                if (firstChange && firstChange.timespan === 168) {
                    let rxStartMs = new Date(this.convertYmdHiToYmd(firstChange.at) + 'T00:00:00');
                    let weekIdx = 0;
                    while (true) {
                        let wStart = new Date(rxStartMs);
                        wStart.setDate(wStart.getDate() + weekIdx * 7);
                        let wEnd = new Date(wStart);
                        wEnd.setDate(wEnd.getDate() + 6);
                        if (wStart.getTime() > endMs.getTime()) break;
                        if (wEnd.getTime() >= startMs.getTime() && wEnd.getTime() <= endMs.getTime()) {
                            let wStartStr = wStart.toISOString().split('T')[0];
                            let wEndStr = wEnd.toISOString().split('T')[0];
                            let rx = getPrescriptionOnDate(med.id, wStartStr);
                            if (rx) {
                                let expected = rx.amount;
                                let logs = this.medicationLogs.filter((l) => {
                                    if (l.med.toLowerCase() !== med.name.toLowerCase()) return false;
                                    let lDate = l.at.substring(0, 10);
                                    return lDate >= wStartStr && lDate <= wEndStr;
                                });
                                let actual = logs.reduce((sum, l) => sum + (parseFloat(l.dose) || 0), 0);
                                totalUnits += 7;
                                if (actual === expected) {
                                    successUnits += 7;
                                } else if (actual > expected) {
                                    overdoseUnits += 7;
                                } else {
                                    underdoseUnits += 7;
                                }
                            }
                        }
                        weekIdx++;
                    }
                }
            });
            if (totalUnits > 0) {
                this.metrics.adherenceRate = Math.min(100, Math.round((successUnits / totalUnits) * 100));
                this.metrics.overdoseRate = Math.min(100, Math.round((overdoseUnits / totalUnits) * 100));
                this.metrics.underdoseRate = Math.min(100, Math.round((underdoseUnits / totalUnits) * 100));
            } else {
                this.metrics.adherenceRate = 100;
                this.metrics.overdoseRate = 0;
                this.metrics.underdoseRate = 0;
            }
            this.metrics.successUnits = successUnits;
            this.metrics.totalUnits = totalUnits;
            this.metrics.overdoseUnits = overdoseUnits;
            this.metrics.underdoseUnits = underdoseUnits;
        },
        setupFlowsheet() {
            let startPoint = new Date(this.startDate);
            let endPoint = new Date(this.endDate);
            let days = [];
            let diffDays = Math.round((endPoint - startPoint) / (24 * 60 * 60 * 1000));
            for (let i = diffDays; i >= 0; i--) {
                let t = new Date(endPoint);
                t.setDate(t.getDate() - i);
                days.push(t.toISOString().split('T')[0]);
            }
            this.flowsheetDays = days.reverse();
            let logsInWindow = this.medicationLogs.filter((log) => {
                let logDay = log.at.substring(0, 10);
                return days.includes(logDay);
            });
            let allMedNames = [...new Set(logsInWindow.map((log) => log.med))].sort();
            this.allFlowsheetMeds = allMedNames; // tüm ilaçlar

            let activeMedNames = allMedNames;
            if (this.selectedMed && this.selectedMed.length > 0) {
                activeMedNames = activeMedNames.filter((m) => this.selectedMed.includes(m));
            }
            if (this.onlyActive) {
                activeMedNames = activeMedNames.filter((m) => this.isMedActiveAtEndDate(m));
            }
            this.uniqueMeds = activeMedNames;
        },
        getMedLogForDay(medName, dayStr) {
            let filtered = this.medicationLogs.filter((l) => {
                return l.med.toLowerCase() === medName.toLowerCase() && l.at.substring(0, 10) === dayStr;
            });
            let baseDose = this.medConversions[medName] || 1;
            let totalTablets = 0;
            let displayLogs = filtered.map((l) => {
                let m = parseFloat(l.dose) / baseDose;
                totalTablets += m;
                let dateParts = l.at.substring(0, 10).split('-');
                let formattedDate = `${dateParts[2]}.${dateParts[1]}.${dateParts[0]}`;
                let time = l.at.substring(11, 16);
                return { ...l, tooltipStr: `* ${m}x : ${formattedDate} ${time}` };
            });
            let displayValue = parseFloat(totalTablets.toFixed(2)).toString();
            return { count: filtered.length, displayValue: displayValue, logs: displayLogs };
        },
        getMedicationStatusOnDate(medId, dateStr) {
            const med = this.medications.find((m) => m.id === medId);
            if (!med) return 'Passive';
            const medData = this.detailedMeds.find((m) => m.name === med.name);
            if (!medData) return 'Passive';
            const date = dateStr;
            const isActive = medData.segments.some((seg) => {
                const segStart = this.convertYmdHiToYmd(seg.s);
                const segEnd = seg.e ? this.convertYmdHiToYmd(seg.e) : null;
                return segStart <= date && (segEnd === null || segEnd >= date);
            });
            return isActive ? 'Active' : 'Passive';
        },
        getMedicationTimespanOnDate(medId, dateStr) {
            let history = this.medicationChanges.filter((c) => c.medication_id === medId && this.convertYmdHiToYmd(c.at) <= dateStr).sort((a, b) => a.at.localeCompare(b.at));
            if (history.length === 0) return null;
            let last = history[history.length - 1];
            return last.timespan;
        },
        getMedicationAmountOnDate(medId, dateStr) {
            let history = this.medicationChanges.filter((c) => c.medication_id === medId && this.convertYmdHiToYmd(c.at) <= dateStr).sort((a, b) => a.at.localeCompare(b.at));
            if (history.length === 0) return 0;
            let last = history[history.length - 1];
            let amount = parseFloat(last.amount) || 0;
            let timespan = parseFloat(last.timespan) || 24;
            return (amount / timespan) * 24;
        },
        getMedicationStatus(medId) {
            return this.getMedicationStatusOnDate(medId, this.endDate);
        },
        getCurrentDoseText(medId) {
            const med = this.medications.find((m) => m.id === medId);
            if (!med) return '';
            const changes = this.medicationChanges
                .filter((c) => c.medication_id === medId && this.convertYmdHiToYmd(c.at) <= this.endDate)
                .filter((c) => !['Ended', 'Paused'].includes(c.type))
                .sort((a, b) => b.at.localeCompare(a.at));
            const latest = changes[0];
            if (!latest) return '';
            return this.formatDoseText(med, latest.amount, latest.timespan);
        },
        formatDoseText(med, amount, timespan) {
            if (med.is_emergency) {
                return `${amount} ${med.unit}`;
            }
            const baseDose = med.base_dose || 1;
            const singleDose = amount / baseDose;
            const formatPill = (val) => {
                return (val % 1 === 0 ? val : val.toFixed(2)).toString().replace('.50', '.5').replace('.00', '').replace('.0', '');
            };
            if (timespan === 168) {
                return `Haftalık ${formatPill(singleDose)}x`;
            } else if (timespan === 72) {
                return `3 Günde 1x${formatPill(singleDose)}`;
            } else if ([8, 12, 24].includes(timespan)) {
                const freq = 24 / timespan;
                return `${freq}x${formatPill(singleDose)}`;
            } else {
                return `${formatPill(singleDose)}x`;
            }
        },
        getLastPrescribedDoseText(medId) {
            const med = this.medications.find((m) => m.id === medId);
            if (!med) return '';
            const changes = this.medicationChanges.filter((c) => c.medication_id === medId && this.convertYmdHiToYmd(c.at) <= this.endDate).sort((a, b) => b.at.localeCompare(a.at));
            const lastPrescription = changes.find((c) => !['Ended', 'Paused'].includes(c.type));
            if (!lastPrescription) return '';
            return this.formatDoseText(med, lastPrescription.amount, lastPrescription.timespan);
        },
        isMedicationActiveInRange(medId) {
            const med = this.medications.find((m) => m.id === medId);
            if (!med) return false;
            const medData = this.detailedMeds.find((m) => m.name === med.name);
            if (!medData) return false;
            const start = this.startDate;
            const end = this.endDate;
            return medData.segments.some((seg) => {
                const segStart = this.convertYmdHiToYmd(seg.s);
                const segEnd = seg.e ? this.convertYmdHiToYmd(seg.e) : null;
                return segStart <= end && (segEnd === null || segEnd >= start);
            });
        },
        updateVisibleMeds() {
            this.detailedMeds = this.medications
                .map((m) => {
                    const mChanges = this.medicationChanges.filter((c) => c.medication_id === m.id).sort((a, b) => a.at.localeCompare(b.at));
                    let segments = [];
                    let curStart = null;
                    mChanges.forEach((c) => {
                        if (['Started', 'Resumed', 'Changed', 'Taken'].includes(c.type)) {
                            if (curStart === null) curStart = c.at;
                            if (c.type === 'Taken') {
                                segments.push({ s: c.at, e: c.at });
                                curStart = null;
                            }
                        } else if (['Ended', 'Paused'].includes(c.type)) {
                            if (curStart !== null) {
                                segments.push({ s: curStart, e: c.at });
                                curStart = null;
                            }
                        }
                    });
                    if (curStart !== null) segments.push({ s: curStart, e: null });
                    return { name: m.name, segments };
                })
                .filter((m) => m.segments.length > 0)
                .sort((a, b) => {
                    const order = ['Panto', 'EcopirinPro', 'Warfmadin', 'Dilatrend', 'BelocZOK', 'Cordarone', 'Augmentin', 'Cipro', 'Tavanic', 'Stafine', 'Mikostatin', 'Levopront', 'GeralginePlus', 'Apikobal', 'Kapril'];
                    return order.indexOf(a.name) - order.indexOf(b.name);
                });
        },
        get visibleMeds() {
            const startMs = new Date(this.startDate + 'T00:00:00').getTime();
            const endMs = new Date(this.endDate + 'T23:59:59').getTime();
            const totalMs = endMs - startMs;
            if (totalMs <= 0) return [];
            return this.detailedMeds
                .filter((m) => this.selectedMed.length === 0 || this.selectedMed.includes(m.name))
                .filter((m) => !this.onlyActive || this.isMedActiveAtEndDate(m.name))
                .map((med) => {
                    let filteredSegments = [];
                    med.segments.forEach((seg) => {
                        const sMs = new Date(seg.s.replace(' ', 'T')).getTime();
                        const eMs = seg.e ? new Date(seg.e.replace(' ', 'T')).getTime() : endMs;
                        if (eMs >= startMs && sMs <= endMs) {
                            const clampedStart = Math.max(sMs, startMs);
                            const clampedEnd = Math.min(eMs, endMs);
                            let left = ((clampedStart - startMs) / totalMs) * 100;
                            let width = ((clampedEnd - clampedStart) / totalMs) * 100;
                            if (width <= 0) width = (86400000 / totalMs) * 100;
                            filteredSegments.push({ left: left.toFixed(2), width: width.toFixed(2), rawStart: seg.s, rawEnd: seg.e || 'Devam Ediyor' });
                        }
                    });
                    return { name: med.name, segments: filteredSegments };
                })
                .filter((med) => med.segments.length > 0);
        },
        get timelineLabels() {
            const start = new Date(this.startDate);
            const end = new Date(this.endDate);
            const totalDiff = end - start;
            if (totalDiff <= 0) return [];
            const labels = [];
            const steps = 5;
            const months = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara'];
            for (let i = 0; i <= steps; i++) {
                const currentMillis = start.getTime() + totalDiff * (i / steps);
                const currentDate = new Date(currentMillis);
                const day = currentDate.getDate();
                const monthStr = months[currentDate.getMonth()];
                labels.push({ text: `${day} ${monthStr}`, isFirstOfMonth: day === 1, percentage: (i / steps) * 100 });
            }
            return labels;
        },
        getTabletCountForChange(change) {
            if (change.type === 'Ended' || change.type === 'Paused') return '';
            const unit = this.getMedicationUnit(change.medication_id);
            const baseDose = this.medConversions[this.getMedicationName(change.medication_id)] || 1;
            const count = change.amount / baseDose;
            const formattedCount = (count % 1 === 0 ? count : count.toFixed(2)).toString().replace('.50', '.5').replace('.00', '').replace('.0', '');
            return `${formattedCount}x`;
        },
        isMedActiveAtEndDate(medName) {
            const med = this.detailedMeds.find((m) => m.name === medName);
            if (!med) return false;
            const date = this.endDate;
            return med.segments.some((seg) => {
                const segStart = this.convertYmdHiToYmd(seg.s);
                const segEnd = seg.e ? this.convertYmdHiToYmd(seg.e) : null;
                return segStart <= date && (segEnd === null || segEnd >= date);
            });
        },
        toggleMed(medName) {
            if (this.selectedMed.includes(medName)) {
                this.selectedMed = this.selectedMed.filter((m) => m !== medName);
            } else {
                this.selectedMed.push(medName);
            }
            this.updateVisibleMeds();
            this.setupFlowsheet();
        },
        clearMedSelection() {
            this.selectedMed = [];
            this.updateVisibleMeds();
            this.setupFlowsheet();
        },
        toggleGroup(groupName) {
            const groupMeds = this.medGroups[groupName];
            const allSelected = groupMeds.every((m) => this.selectedMed.includes(m));
            if (allSelected) {
                this.selectedMed = this.selectedMed.filter((m) => !groupMeds.includes(m));
            } else {
                groupMeds.forEach((m) => {
                    if (!this.selectedMed.includes(m)) this.selectedMed.push(m);
                });
            }
            this.updateVisibleMeds();
            this.setupFlowsheet();
        },
        isGroupActive(groupName) {
            const groupMeds = this.medGroups[groupName];
            return groupMeds.every((m) => this.selectedMed.includes(m));
        },
        getTabletCount(dayEvent) {
            if (dayEvent.type === 'end' || dayEvent.type === 'pause') return '';
            const med = this.medications.find((m) => m.name === dayEvent.med);
            if (!med) return '';
            const change = this.medicationChanges.find((c) => c.medication_id === med.id && c.at === dayEvent.date);
            if (!change) return '';
            const factor = med.base_dose || 1;
            const formatDose = (val) => {
                return (val % 1 === 0 ? val : val.toFixed(2)).toString().replace('.50', '.5').replace('.00', '').replace('.0', '');
            };
            const singleDose = change.amount / factor;
            if (change.timespan === 168) {
                return `Haftalık ${formatDose(singleDose)}x`;
            } else if (change.timespan === 72) {
                return `3 Günde 1x${formatDose(singleDose)}`;
            } else if ([8, 12, 24].includes(change.timespan)) {
                const freq = 24 / change.timespan;
                return `${freq}x${formatDose(singleDose)}`;
            } else {
                return `${formatDose(singleDose)}x`;
            }
        },
        formatTurkishDate(isoDate) {
            if (!isoDate) return '-';
            const datePart = isoDate.includes(' ') ? isoDate.split(' ')[0] : isoDate;
            const parts = datePart.split('-');
            if (parts.length !== 3) return isoDate;
            return `${parts[2]}.${parts[1]}.${parts[0]}`;
        },
        getLastKnownLab(code) {
            const sortedTests = [...this.tests].filter((t) => t.at.substring(0, 10) <= this.endDate).sort((a, b) => new Date(b.at) - new Date(a.at));
            for (let test of sortedTests) {
                let item = this.testItems.find((ti) => ti.test_id === test.id && ti.code === code);
                if (item) {
                    return { val: item.result, date: this.formatTurkishDate(test.at.substring(0, 10)) };
                }
            }
            return null;
        },
        getTrendDataForCode(code) {
            let allPoints = [];
            this.tests.forEach((t) => {
                let item = this.testItems.find((ti) => ti.test_id === t.id && ti.code === code);
                if (item) {
                    allPoints.push({ val: parseFloat(item.result), date: t.at.substring(0, 10), rawDate: t.at });
                }
            });
            allPoints.sort((a, b) => new Date(a.rawDate) - new Date(b.rawDate));
            let insideRange = allPoints.filter((p) => p.date >= this.startDate && p.date <= this.endDate);
            let beforeRange = allPoints.filter((p) => p.date < this.startDate);
            let finalPoints = [];
            if (insideRange.length >= 2) {
                if (beforeRange.length > 0) {
                    finalPoints.push(beforeRange[beforeRange.length - 1]);
                }
                finalPoints = finalPoints.concat(insideRange);
            } else if (insideRange.length === 1) {
                finalPoints = [...insideRange];
                let idx = beforeRange.length - 1;
                while (finalPoints.length < 2 && idx >= 0) {
                    finalPoints.unshift(beforeRange[idx]);
                    idx--;
                }
            } else {
                let idx = beforeRange.length - 1;
                while (finalPoints.length < 2 && idx >= 0) {
                    finalPoints.unshift(beforeRange[idx]);
                    idx--;
                }
            }
            return finalPoints;
        },
        get periodicClinicalReport() {
            if (!this.startDate || !this.endDate) return 'Tarih aralığı seçilmedi.';
            const startStr = this.formatTurkishDate(this.startDate);
            const endStr = this.formatTurkishDate(this.endDate);
            let bpText = '';
            const currentBpList = this.getFilteredPressures();
            if (currentBpList.length > 0) {
                bpText = `${startStr} - ${endStr} tarihleri arasında toplam ${currentBpList.length} adet tansiyon ölçümü yapılmıştır. Dönem ortalaması ${this.metrics.avgSys}/${this.metrics.avgDia} mmHg olarak hesaplanmıştır ve bu genel olarak "${this.metrics.bpStatusText}" kategorisindedir.`;
                if (this.previousAvgBp !== '-') {
                    bpText += ` Bir önceki dönem ortalaması ile kıyaslandığında değişim trendi ${this.previousAvgBp} mmHg olarak gerçekleşmiştir.`;
                }
            } else {
                bpText = `${startStr} - ${endStr} tarihleri arasında kaydedilmiş herhangi bir tansiyon ölçümü bulunmamaktadır.`;
            }
            let weightText = '';
            if (this.metrics.currentWeight > 0) {
                weightText = `Seçilen dönem sonu itibarıyla güncel kilo ${this.metrics.currentWeight} kg'dır.`;
                if (this.metrics.weightDelta !== 0) {
                    const direction = this.metrics.weightDelta > 0 ? 'artış' : 'azalış';
                    weightText += ` Dönem başına (${this.metrics.startWeight} kg) göre ${Math.abs(this.metrics.weightDelta)} kg'lık bir ${direction} gözlemlenmiştir.`;
                } else {
                    weightText += ` Dönem boyunca kilo stabil seyretmiştir.`;
                }
            } else {
                weightText = `${startStr} - ${endStr} tarihleri arasında kilo kaydı bulunmamaktadır.`;
            }
            let labText = '';
            let validTests = this.tests.filter((t) => t.at.substring(0, 10) <= this.endDate);
            if (validTests.length > 0) {
                const getLatestAndPrevValue = (code) => {
                    let items = [];
                    validTests.forEach((t) => {
                        this.testItems
                            .filter((item) => item.test_id === t.id && item.code === code)
                            .forEach((item) => {
                                items.push({ val: parseFloat(item.result), date: t.at });
                            });
                    });
                    items.sort((a, b) => new Date(b.date) - new Date(a.date));
                    return { latest: items[0], previous: items[1] };
                };
                const targetCodes = ['INR', 'HGB', 'WBC', 'CRP'];
                let labDetails = [];
                targetCodes.forEach((code) => {
                    const { latest, previous } = getLatestAndPrevValue(code);
                    if (latest) {
                        let detail = `${code}: ${latest.val}`;
                        if (previous) {
                            const diff = (latest.val - previous.val).toFixed(2);
                            detail += ` (Bir önceki ${this.formatTurkishDate(previous.date.substring(0, 10))} tarihindeki ölçüme göre: ${diff >= 0 ? '+' : ''}${diff})`;
                        }
                        labDetails.push(detail);
                    }
                });
                if (labDetails.length > 0) {
                    labText = `${endStr} tarihi ve öncesindeki son laboratuvar verilerine göre kritik parametre durumları şu şekildedir: ${labDetails.join(', ')}.`;
                    if (this.metrics.outOfBoundsCount > 0) {
                        const outCodes = this.metrics.outOfBoundsList.map((i) => `${i.code} (${i.status})`).join(', ');
                        labText += ` Bu dönemde referans aralığı dışında kalan parametreler: ${outCodes}.`;
                    } else {
                        labText += ` Dönem sonu itibarıyla takip edilen tüm tahliller referans aralığı içerisinde normal seyretmektedir.`;
                    }
                } else {
                    labText = `Belirtilen tarihlerde hedeflenen kritik tahlil parametrelerine (INR, HGB, WBC, CRP) ait kayıt bulunamadı.`;
                }
            } else {
                labText = `${startStr} öncesi ve sonrasını kapsayan herhangi bir tahlil kaydı bulunmamaktadır.`;
            }
            let medText = '';
            let currentPeriodMeds = [];
            const getPrescriptionOnDate = (medId, dateStr) => {
                let validChanges = this.medicationChanges.filter((c) => c.medication_id === medId && c.at.substring(0, 10) <= dateStr).sort((a, b) => new Date(b.at) - new Date(a.at));
                return validChanges.length > 0 ? validChanges[0] : null;
            };
            this.medications.forEach((med) => {
                let pStart = getPrescriptionOnDate(med.id, this.startDate);
                let pEnd = getPrescriptionOnDate(med.id, this.endDate);
                let wasActive = pStart && pStart.is_active;
                let isActiveNow = pEnd && pEnd.is_active;
                let doseChanged = wasActive && isActiveNow && pStart.dosage !== pEnd.dosage;
                if (isActiveNow || wasActive || doseChanged) {
                    currentPeriodMeds.push({ name: med.name, wasActive, isActiveNow, doseChanged, startDose: pStart ? pStart.dosage : null, endDose: pEnd ? pEnd.dosage : null, targetDose: med.target_dosage });
                }
            });
            let medDetails = [];
            currentPeriodMeds.forEach((m) => {
                if (m.wasActive && !m.isActiveNow) {
                    medDetails.push(`${m.name} (Bu dönemde kullanımı sonlandırıldı)`);
                } else if (!m.wasActive && m.isActiveNow) {
                    medDetails.push(`${m.name} (Bu dönemde yeni başlandı, Doz: ${m.endDose})`);
                } else if (m.doseChanged) {
                    medDetails.push(`${m.name} (Doz Değişikliği: ${m.startDose} -> ${m.endDose})`);
                } else if (m.isActiveNow) {
                    let doseWarn = m.endDose !== m.targetDose ? ` [Dikkat: Alınan Doz: ${m.endDose}, Hedeflenen Doz: ${m.targetDose}]` : '';
                    medDetails.push(`${m.name} (Doz: ${m.endDose}${doseWarn})`);
                }
            });
            if (medDetails.length > 0) {
                medText = `${startStr} ile ${endStr} tarihleri arasında tedavi şeması ve ilaç durumları: ${medDetails.join('; ')}.`;
                medText += ` Bu dönem genelinde tedaviye uyum oranı %${this.metrics.adherenceRate} olarak kaydedilmiştir.`;
            } else {
                medText = `Seçilen dönemde aktif bir ilaç veya tedavi değişim kaydı bulunmamaktadır.`;
            }
            return `KLİNİK DEĞERLENDİRME RAPORU (${startStr} - ${endStr})\n\n` + `1. TANSİYON TRENDİ:\n${bpText}\n\n` + `2. KİLO VE SIVI DURUMU:\n${weightText}\n\n` + `3. LABORATUVAR ANALİZLERİ:\n${labText}\n\n` + `4. İLAÇ TEDAVİSİ VE UYUM:\n${medText}`;
        },
        generateDynamicInsight(startDate, endDate) {
            if (!startDate || !endDate) {
                return `<div class="p-4 sm:p-6 text-center text-xs sm:text-sm font-medium text-slate-400 italic bg-slate-50/50 rounded-xl border border-dashed border-slate-200">Klinik verileriniz analiz ediliyor, lütfen geçerli bir tarih aralığı seçtiğinizden emin olun...</div>`;
            }
            const startD = new Date(startDate);
            const endD = new Date(endDate);
            if (isNaN(startD.getTime()) || isNaN(endD.getTime())) {
                return `<div class="p-4 sm:p-6 text-center text-xs sm:text-sm text-slate-400">Tarih aralığı geçersiz.</div>`;
            }
            const msPerDay = 86400000;
            const periodDays = Math.round((endD - startD) / msPerDay) + 1;
            const prevEndD = new Date(startD.getTime() - msPerDay);
            const prevStartD = new Date(prevEndD.getTime() - (periodDays - 1) * msPerDay);
            const prevStartStr = prevStartD.toISOString().split('T')[0];
            const prevEndStr = prevEndD.toISOString().split('T')[0];
            const l7StartD = new Date(endD.getTime() - 6 * msPerDay);
            const p7EndD = new Date(l7StartD.getTime() - msPerDay);
            const p7StartD = new Date(p7EndD.getTime() - 6 * msPerDay);
            const l7StartStr = l7StartD.toISOString().split('T')[0];
            const p7StartStr = p7StartD.toISOString().split('T')[0];
            const p7EndStr = p7EndD.toISOString().split('T')[0];
            const getDayName = (dateStr) => {
                const d = new Date(dateStr.substring(0, 10));
                if (isNaN(d.getTime())) return '';
                return ['Pazar', 'Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi'][d.getDay()];
            };
            const formatDateNatural = (dateStr) => {
                if (!dateStr) return '';
                let d = new Date(dateStr.substring(0, 10));
                const m = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'];
                return `${d.getDate()} ${m[d.getMonth()]}`;
            };
            const getRecordsInRange = (arr, start, end) => {
                return arr
                    .filter((item) => {
                        const d = item.at.substring(0, 10);
                        return d >= start && d <= end;
                    })
                    .sort((a, b) => a.at.localeCompare(b.at));
            };
            const getBpStats = (records) => {
                if (!records || records.length === 0) return null;
                let sys = records.map((r) => r.sys);
                let dia = records.map((r) => r.dia);
                let maxSysRec = records.reduce((max, r) => (r.sys > max.sys ? r : max), records[0]);
                let minSysRec = records.reduce((min, r) => (r.sys < min.sys ? r : min), records[0]);
                return { minSys: Math.min(...sys), maxSys: Math.max(...sys), minDia: Math.min(...dia), maxDia: Math.max(...dia), avgSys: Math.round(sys.reduce((a, b) => a + b, 0) / sys.length), avgDia: Math.round(dia.reduce((a, b) => a + b, 0) / dia.length), count: records.length, maxSysRec, minSysRec };
            };
            const getWeightStats = (records) => {
                if (!records || records.length === 0) return null;
                let sorted = [...records].sort((a, b) => a.at.localeCompare(b.at));
                let first = sorted[0].weight;
                let last = sorted[sorted.length - 1].weight;
                let maxWtRec = records.reduce((max, r) => (r.weight > max.weight ? r : max), records[0]);
                let minWtRec = records.reduce((min, r) => (r.weight < min.weight ? r : min), records[0]);
                return { first, last, diff: parseFloat((last - first).toFixed(1)), count: records.length, maxWtRec, minWtRec };
            };
            let allPressures = getRecordsInRange(this.pressures, startDate, endDate);
            let allWeights = getRecordsInRange(this.weights, startDate, endDate);
            let allDates = [...allPressures, ...allWeights].sort((a, b) => b.at.localeCompare(a.at));
            let lastRecordDateStr = allDates.length > 0 ? allDates[0].at.substring(0, 10) : endDate;
            let insight = `<div class="mb-4 pb-4 border-b border-slate-100"><p class="text-[11px] sm:text-xs font-medium text-slate-600 leading-relaxed">Seçmiş olduğunuz <b>${this.formatFullDate(startDate)}</b> ile <b>${this.formatFullDate(endDate)}</b> tarihleri arasındaki <b>${periodDays} günlük</b> klinik veri akışınız yapay zeka destekli sistemimiz tarafından incelendi. Mekanik aort kapak ve diseksiyon onarımı öykünüze özel olarak derlenen analiz raporunuz aşağıdadır:</p></div>`;
            let bpHtml = `<div class="mb-5 sm:mb-6"><h4 class="text-xs sm:text-sm font-bold tracking-tight text-indigo-700 mb-2 flex items-center gap-2"><span class="h-2 w-2 sm:h-2.5 sm:w-2.5 rounded-full bg-blue-500 shadow-sm shadow-blue-200"></span> 1. Tansiyon ve Aort Stresi (Hemodinami)</h4><div class="pl-3 sm:pl-4 border-l-2 border-slate-100 space-y-3">`;
            let selBp = getBpStats(allPressures);
            if (selBp) {
                let lastBpDateStr = allPressures[allPressures.length - 1].at.substring(0, 10);
                let todayBp = getBpStats(getRecordsInRange(allPressures, lastBpDateStr, lastBpDateStr));
                let prevBpRecords = allPressures.filter((p) => p.at.substring(0, 10) < lastBpDateStr);
                let prevBpDateStr = prevBpRecords.length > 0 ? prevBpRecords[prevBpRecords.length - 1].at.substring(0, 10) : null;
                let yesterdayBp = prevBpDateStr ? getBpStats(getRecordsInRange(allPressures, prevBpDateStr, prevBpDateStr)) : null;
                let l7Bp = getBpStats(getRecordsInRange(this.pressures, l7StartStr, endDate));
                let p7Bp = getBpStats(getRecordsInRange(this.pressures, p7StartStr, p7EndStr));
                let prevPeriodBp = getBpStats(getRecordsInRange(this.pressures, prevStartStr, prevEndStr));
                let dayTxt = `<b>Günlük İzlem:</b> Dönem içindeki en son ölçüm gününüz olan <b>${this.formatFullDate(lastBpDateStr)} (${getDayName(lastBpDateStr)})</b> tarihinde tansiyon ortalamanız <b>${todayBp ? todayBp.avgSys : selBp.avgSys}/${todayBp ? todayBp.avgDia : selBp.avgDia} mmHg</b> olarak gerçekleşmiş. `;
                if (yesterdayBp && todayBp) {
                    let diff = todayBp.avgSys - yesterdayBp.avgSys;
                    if (diff >= 3) dayTxt += `Ondan bir önceki ölçüm gününe (${this.formatFullDate(prevBpDateStr)}) kıyasla ortalamada <b>${diff} mmHg'lik bir yükseliş</b> söz konusu. `;
                    else if (diff <= -3) dayTxt += `Önceki ölçüm gününe göre <b>${Math.abs(diff)} mmHg'lik bir düşüş</b> var; bu damar içi basıncınızın azalması anlamına gelir ve kalbiniz için olumludur. `;
                    else dayTxt += `Tansiyonunuz bir önceki güne göre <b>oldukça stabil</b> kalmış. `;
                }
                let weekTxt = `<b>Haftalık Trend:</b> Seçili dönemin son 7 gününde kan basıncı ortalamanız <b>${l7Bp.avgSys}/${l7Bp.avgDia} mmHg</b>. `;
                weekTxt += `Bu hafta ulaştığınız <b>en yüksek değer ${getDayName(l7Bp.maxSysRec.at)} günü ${l7Bp.maxSys}/${l7Bp.maxDia}</b>, <b>en düşük değer ise ${getDayName(l7Bp.minSysRec.at)} günü ${l7Bp.minSys}/${l7Bp.minDia}</b> olmuş. `;
                if (p7Bp) {
                    let diff = l7Bp.avgSys - p7Bp.avgSys;
                    if (diff >= 4) weekTxt += `Geçen haftanın ortalamasına (${p7Bp.avgSys}/${p7Bp.avgDia}) kıyasla <b>belirgin bir yükseliş eğilimi</b> var. `;
                    else if (diff <= -4) weekTxt += `Geçen haftanın ortalamasına kıyasla <b>güzel bir rahatlama (düşüş) trendi</b> görülüyor. `;
                    else weekTxt += `Geçen haftanın ortalamasıyla (${p7Bp.avgSys}/${p7Bp.avgDia}) <b>hemen hemen aynı</b> seviyelerde ilerliyorsunuz. `;
                }
                let periodTxt = `<b>Dönem Özeti (${periodDays} Gün):</b> Bu geniş aralıkta toplam <b>${selBp.count} kez</b> tansiyon ölçmüşsünüz ve genel ortalamanız <b>${selBp.avgSys}/${selBp.avgDia} mmHg</b> çıkmış. `;
                if (prevPeriodBp) {
                    let diff = selBp.avgSys - prevPeriodBp.avgSys;
                    if (diff > 3) periodTxt += `Bir önceki döneme (${prevPeriodBp.avgSys}/${prevPeriodBp.avgDia}) göre genel ortalamanızda maalesef artış yaşanmış. `;
                    else if (diff < -3) periodTxt += `Bir önceki döneme göre genel tansiyon ortalamanız aşağı çekilmiş, tebrikler. `;
                    else periodTxt += `Geçmiş dönemle karşılaştırdığımızda genel ortalamanızı çok istikrarlı bir şekilde korumuşsunuz. `;
                }
                let wallStressWarning =
                    selBp.maxSys >= 135
                        ? `<div class="mt-2 text-rose-700 bg-rose-50 border border-rose-200 p-2.5 rounded-lg shadow-sm">⚠️ <b>Damar Basıncı Uyarısı:</b> Bentall operasyonu geçirmiş biri olarak, bu dönemde tansiyonunuzun <b>${selBp.maxSys} mmHg</b> seviyelerine çıkması risklidir. Hedefimiz 120-130 bandının altında kalmaktır. Doktorunuzla antihipertansif dozlarını görüşmelisiniz.</div>`
                        : `<div class="mt-2 text-emerald-700 bg-emerald-50 border border-emerald-200 p-2.5 rounded-lg shadow-sm">✅ <b>Damar Güvenliği:</b> Bu dönemdeki zirve tansiyonunuz (<b>${selBp.maxSys} mmHg</b>) onarılan aort damarınıza zarar vermeyecek kadar güvenli bir aralıkta.</div>`;
                bpHtml += `<div class="text-[11px] sm:text-xs text-slate-700 leading-relaxed space-y-2"><p>${dayTxt}</p><p>${weekTxt}</p><p>${periodTxt}</p>${wallStressWarning}</div>`;
            } else {
                bpHtml += `<p class="text-[11px] sm:text-xs text-slate-500 italic">Bu döneme ait herhangi bir tansiyon ölçüm kaydı bulunmamaktadır.</p>`;
            }
            bpHtml += `</div></div>`;
            insight += bpHtml;
            let wtHtml = `<div class="mb-5 sm:mb-6"><h4 class="text-xs sm:text-sm font-bold tracking-tight text-indigo-700 mb-2 flex items-center gap-2"><span class="h-2 w-2 sm:h-2.5 sm:w-2.5 rounded-full bg-amber-500 shadow-sm shadow-amber-200"></span> 2. Kilo ve Sıvı Dengesi (Ödem Takibi)</h4><div class="pl-3 sm:pl-4 border-l-2 border-slate-100 space-y-3">`;
            let selWt = getWeightStats(allWeights);
            if (selWt) {
                let lastWtDateStr = allWeights[allWeights.length - 1].at.substring(0, 10);
                let todayWt = getWeightStats(getRecordsInRange(allWeights, lastWtDateStr, lastWtDateStr));
                let prevWtRecords = allWeights.filter((w) => w.at.substring(0, 10) < lastWtDateStr);
                let prevWtDateStr = prevWtRecords.length > 0 ? prevWtRecords[prevWtRecords.length - 1].at.substring(0, 10) : null;
                let yesterdayWt = prevWtDateStr ? getWeightStats(getRecordsInRange(allWeights, prevWtDateStr, prevWtDateStr)) : null;
                let l7Wt = getWeightStats(getRecordsInRange(this.weights, l7StartStr, endDate));
                let p7Wt = getWeightStats(getRecordsInRange(this.weights, p7StartStr, p7EndStr));
                let dayTxt = `<b>Günlük İzlem:</b> ${this.formatFullDate(lastWtDateStr)} tarihindeki en son tartımınıza göre kilonuz <b>${todayWt.last} kg</b>. `;
                if (yesterdayWt) {
                    let diff = todayWt.last - yesterdayWt.last;
                    if (diff >= 0.5) dayTxt += `Önceki ölçüme (${yesterdayWt.last} kg) göre <b>+${diff.toFixed(1)} kg'lık</b> ani bir artış var. `;
                    else if (diff <= -0.5) dayTxt += `Önceki ölçüme göre <b>${Math.abs(diff).toFixed(1)} kg'lık</b> bir hafifleme söz konusu. `;
                    else dayTxt += `Önceki güne kıyasla kilonuz <b>tamamen stabil</b> kalmış. `;
                }
                let weekTxt = '';
                if (l7Wt) {
                    weekTxt = `<b>Haftalık Trend:</b> Son 7 gün içinde kilonuz <b>${l7Wt.first} kg'dan ${l7Wt.last} kg'a</b> gelerek net <b>${l7Wt.diff > 0 ? '+' + l7Wt.diff : l7Wt.diff} kg</b> değişim göstermiş. `;
                    if (p7Wt) {
                        if (l7Wt.diff > 0.5 && p7Wt.diff <= 0) weekTxt += `Geçen haftanın aksine bu hafta kilo alımı yönünde ivme kazanmışsınız. `;
                        else if (l7Wt.diff < -0.5 && p7Wt.diff >= 0) weekTxt += `Geçen haftanın aksine bu hafta kilo verme eğilimine girmişsiniz. `;
                    }
                }
                let periodTxt = `<b>Dönem Özeti:</b> Tüm bu süreçte kümülatif değişime bakarsak dönemi <b>${selWt.diff > 0 ? '+' + selWt.diff : selWt.diff} kg</b> farkla kapatmışsınız. `;
                let fluidWarning =
                    l7Wt && l7Wt.diff >= 1.5
                        ? `<div class="mt-2 text-amber-700 bg-amber-50 border border-amber-200 p-2.5 rounded-lg shadow-sm">⚠️ <b>Sıvı Retansiyonu Riski:</b> Son günlerdeki <b>+${l7Wt.diff} kg'lık</b> hızlı artış, kalp yetmezliğine bağlı ödem kaynaklı olabilir. Nefes darlığı varsa doktorunuza başvurunuz.</div>`
                        : `<div class="mt-2 text-emerald-700 bg-emerald-50 border border-emerald-200 p-2.5 rounded-lg shadow-sm">✅ Kilonuzda vücutta tehlikeli bir sıvı birikimini işaret eden ekstrem bir dalgalanma saptanmadı.</div>`;
                wtHtml += `<div class="text-[11px] sm:text-xs text-slate-700 leading-relaxed space-y-2"><p>${dayTxt}</p><p>${weekTxt}</p><p>${periodTxt}</p>${fluidWarning}</div>`;
            } else {
                wtHtml += `<p class="text-[11px] sm:text-xs text-slate-500 italic">Bu döneme ait kilo ölçüm kaydı bulunmamaktadır.</p>`;
            }
            wtHtml += `</div></div>`;
            insight += wtHtml;
            let labHtml = `<div class="mb-5 sm:mb-6"><h4 class="text-xs sm:text-sm font-bold tracking-tight text-indigo-700 mb-2 flex items-center gap-2"><span class="h-2 w-2 sm:h-2.5 sm:w-2.5 rounded-full bg-purple-500 shadow-sm shadow-purple-200"></span> 3. Laboratuvar Bulguları ve Kapak Sağlığı</h4><div class="pl-3 sm:pl-4 border-l-2 border-slate-100 space-y-3">`;
            let sortedTests = [...this.tests].filter((t) => t.at.substring(0, 10) <= endDate).sort((a, b) => new Date(b.at) - new Date(a.at));
            if (sortedTests.length > 0) {
                let latestTest = sortedTests[0];
                let currTestItems = this.testItems.filter((ti) => ti.test_id === latestTest.id);
                labHtml += `<p class="text-[11px] sm:text-xs text-slate-700 leading-relaxed">En güncel laboratuvar kan tahliliniz <b>${this.formatFullDate(latestTest.at.substring(0, 10))}</b> tarihinde yapılmış. Bu tahlil sonuçlarınızı geçmişteki tıbbi kayıtlarınızla birleştirip klinik olarak değerlendirdiğimde şu tabloyu görüyorum:</p>`;
                let paragraphs = [];
                const getLabData = (code) => {
                    let curr = currTestItems.find((ti) => ti.code.toUpperCase() === code);
                    if (!curr) return null;
                    let val = parseFloat(curr.result);
                    let status = this.getLabItemStatus(curr);
                    let prevItem = null;
                    let prevDate = null;
                    for (let i = 1; i < sortedTests.length; i++) {
                        let pItem = this.testItems.find((ti) => ti.test_id === sortedTests[i].id && ti.code.toUpperCase() === code);
                        if (pItem) {
                            prevItem = pItem;
                            prevDate = sortedTests[i].at.substring(0, 10);
                            break;
                        }
                    }
                    let prev = prevItem ? parseFloat(prevItem.result) : null;
                    return { val, prev, status, name: curr.name, prevDate };
                };
                let inr = getLabData('INR'),
                    pt = getLabData('PT'),
                    aptt = getLabData('APTT'),
                    plt = getLabData('PLT');
                let alt = getLabData('ALT'),
                    ast = getLabData('AST');
                let crea = getLabData('CREA'),
                    bun = getLabData('BUN');
                let wbc = getLabData('WBC'),
                    crp = getLabData('CRP');
                let hgb = getLabData('HGB');
                if (inr || pt || aptt || plt) {
                    let pText = `<b>Kapak Koruması ve Kan Sulandırma:</b> Kapak koruması için kritik değerlerinize baktığımda; `;
                    if (inr) {
                        pText += `en önemli göstergemiz olan INR değeriniz ${inr.val.toFixed(2)} çıkmış. `;
                        if (inr.prev !== null) {
                            let diff = inr.val - inr.prev;
                            if (diff > 0.05) pText += `Bu, bir önceki ${inr.prev.toFixed(2)} değerinize göre hafif yükseldiğini gösteriyor `;
                            else if (diff < -0.05) pText += `Bu, bir önceki ${inr.prev.toFixed(2)} ölçümünden biraz gerilediğini gösteriyor `;
                            else pText += `Bu, bir önceki tahlilinizle neredeyse tamamen aynı kalmış `;
                        }
                        if (inr.val < 2.0) {
                            pText += `ve <span class="text-rose-600 font-bold">maalesef sizin için gereken hedefin altında. Pıhtı riskine karşı doktorunuzun kan sulandırıcı hap dozajını artırması çok önemli.</span> `;
                        } else if (inr.val > 3.0) {
                            pText += `fakat <span class="text-orange-600 font-bold">istediğimiz değerin de üstünde. Kanınız fazla sulandığı için ufak çaplı kanama riski oluşabilir, tedbirli olmalısınız.</span> `;
                        } else {
                            pText += `ve <span class="text-emerald-600 font-bold">tam istediğimiz güvenli seviyelerde, bu sizin için çok iyi bir durum.</span> `;
                        }
                    }
                    if (pt || aptt) {
                        pText += `Pıhtılaşma süreniz de genel hatlarıyla uyumlu; `;
                        if (pt) pText += `PT ${pt.val.toFixed(1)} saniye${pt.prev ? `(önceki:${pt.prev.toFixed(1)})` : ''}, `;
                        if (aptt) pText += `APTT ise ${aptt.val.toFixed(1)} saniye${aptt.prev ? `(önceki:${aptt.prev.toFixed(1)})` : ''} ölçülmüş. `;
                    }
                    if (plt) {
                        pText += `Trombosit (PLT) hücreleriniz ise ${plt.val.toFixed(0)} ölçülmüş; `;
                        if (plt.prev !== null) {
                            if (plt.val > plt.prev + 15) pText += `bir önceki ${plt.prev.toFixed(0)} değerine göre biraz daha yüksek.`;
                            else if (plt.val < plt.prev - 15) pText += `bir önceki ${plt.prev.toFixed(0)} değerine göre bir tık gerilemiş.`;
                            else pText += `geçmişteki ${plt.prev.toFixed(0)} ölçümüne göre aşağı yukarı aynı kalmış.`;
                        } else {
                            pText += `sınırlar içinde seyrediyor.`;
                        }
                    }
                    paragraphs.push(pText);
                }
                if (alt || ast) {
                    let pText = `<b>Karaciğer Durumu:</b> Karaciğerinize gelirsek; `;
                    if ((alt && alt.prev !== null) || (ast && ast.prev !== null)) {
                        let improving = false;
                        let worsening = false;
                        if (alt && alt.prev && alt.val < alt.prev - 5) improving = true;
                        if (alt && alt.prev && alt.val > alt.prev + 5) worsening = true;
                        if (improving) {
                            pText += `<span class="text-emerald-600 font-bold">Karaciğer yorgunluğunuz iyiye gidiyor.</span> `;
                            if (alt) pText += `ALT değeriniz ${alt.prev.toFixed(0)}'den ${alt.val.toFixed(0)}'ye, `;
                            if (ast) pText += `AST değeriniz ise ${ast.prev.toFixed(0)}'den ${ast.val.toFixed(0)}'ye düşmüş. `;
                        } else if (worsening) {
                            pText += `<span class="text-amber-600 font-bold">Karaciğer enzimlerinizde ilaç kullanımına veya beslenmeye bağlı hafif bir yükseliş/yorgunluk var.</span> `;
                            if (alt) pText += `ALT ${alt.prev.toFixed(0)}'den ${alt.val.toFixed(0)}'ye, `;
                            if (ast) pText += `AST ${ast.prev.toFixed(0)}'den ${ast.val.toFixed(0)}'ye çıkmış. `;
                        } else {
                            pText += `Enzimleriniz önceki ölçümlere oldukça paralel ve stabil seyrediyor (ALT: ${alt ? alt.val.toFixed(0) : '-'}, AST: ${ast ? ast.val.toFixed(0) : '-'}). `;
                        }
                    } else {
                        pText += `ALT (${alt ? alt.val.toFixed(0) : '-'}) ve AST (${ast ? ast.val.toFixed(0) : '-'}) enzimleriniz normal seyrediyor. `;
                    }
                    paragraphs.push(pText);
                }
                if (crea || bun) {
                    let pText = `<b>Böbrek Fonksiyonları:</b> Böbrek süzme değerleriniz `;
                    if (crea) {
                        pText += `Kreatinin bazında ${crea.val.toFixed(2)} ölçülmüş. `;
                        if (crea.prev !== null) {
                            let diff = crea.val - crea.prev;
                            if (diff > 0.1) pText += `Geçen seferki ${crea.prev.toFixed(2)} ölçümüne göre hafif yükselmiş. `;
                            else if (diff < -0.1) pText += `Geçen seferki ${crea.prev.toFixed(2)} ölçümüne kıyasla daha iyi durumda (düşmüş). `;
                            else pText += `Geçmiş tahlille tamamen stabil kalmış. `;
                        }
                        if (crea.status === 'Yüksek') pText += `<span class="text-amber-600 font-medium">Böbreklerinizin yorulmaması için günlük sıvı tüketiminize mutlaka dikkat edin.</span> `;
                    }
                    paragraphs.push(pText);
                }
                if (wbc || crp) {
                    let pText = `<b>Enfeksiyon ve İltihap:</b> Vücuttaki enfeksiyon durumu için `;
                    if (wbc) pText += `Beyaz kan hücresi (WBC) ${wbc.val.toFixed(2)} çıkarken${wbc.prev ? `,geçmişte bu ${wbc.prev.toFixed(2)}imiş` : ''}. `;
                    if (crp) pText += `Akut iltihap (CRP) değeriniz ${crp.val.toFixed(1)} olarak görülüyor${crp.prev ? `(önceki:${crp.prev.toFixed(1)})` : ''}. `;
                    if ((wbc && wbc.status === 'Yüksek') || (crp && crp.status === 'Yüksek')) {
                        pText += `<span class="text-rose-600 font-bold">Bu değerlerin yüksek kalması, mekanik kalp kapağınıza enfeksiyon oturması riski (endokardit) nedeniyle istenmeyen bir durumdur; ateşe ve halsizliğe karşı tetikte olunuz.</span>`;
                    } else {
                        pText += `<span class="text-emerald-600 font-bold">Vücutta aktif veya tehlikeli bir enfeksiyon görünmüyor, değerler gayet temiz.</span>`;
                    }
                    paragraphs.push(pText);
                }
                if (hgb) {
                    let pText = `<b>Kansızlık (Anemi):</b> Kan değeriniz olan Hemoglobin (HGB) ${hgb.val.toFixed(1)} çıkmış. `;
                    if (hgb.prev !== null) {
                        if (hgb.val > hgb.prev + 0.5) pText += `Eski ${hgb.prev.toFixed(1)} ölçümünüze kıyasla çok güzel toparlamış ve artmış. `;
                        else if (hgb.val < hgb.prev - 0.5) pText += `Eski ${hgb.prev.toFixed(1)} ölçümünüze göre biraz düşüş görünüyor. `;
                    }
                    if (hgb.status === 'Düşük') pText += `<span class="text-amber-600 font-medium">Ancak hala normalin biraz altında; bu durum kalbin daha çok yorulmasına neden olur. Gerekirse doktorunuzdan demir/vitamin takviyesi talep edebilirsiniz.</span>`;
                    paragraphs.push(pText);
                }
                let otherAbnormals = [];
                currTestItems.forEach((currItem) => {
                    let code = currItem.code.toUpperCase();
                    if (!['INR', 'PT', 'APTT', 'PLT', 'ALT', 'AST', 'CREA', 'BUN', 'WBC', 'CRP', 'HGB', 'HCT'].includes(code)) {
                        if (this.getLabItemStatus(currItem) !== 'Normal') {
                            otherAbnormals.push(`${code} (${parseFloat(currItem.result).toFixed(2)})`);
                        }
                    }
                });
                if (otherAbnormals.length > 0) {
                    paragraphs.push(`<b>Diğer Gözlemler:</b> Son tahlilinizde yukarıdakilere ek olarak, ${otherAbnormals.join(', ')} değerlerinde sınır dışı ufak sapmalar bulunmuş.`);
                }
                if (paragraphs.length > 0) {
                    labHtml += `<div class="mt-3 space-y-3 bg-slate-50/50 p-4 rounded-xl border border-slate-200/80">`;
                    paragraphs.forEach((pt) => {
                        labHtml += `<p class="text-[11px] sm:text-xs text-slate-700 leading-relaxed">${pt}</p>`;
                    });
                    labHtml += `</div>`;
                } else {
                    labHtml += `<p class="text-[11px] sm:text-xs text-slate-500 italic mt-2">Bu tahlil seansında standart klinik parametrelere rastlanmadı.</p>`;
                }
            } else {
                labHtml += `<p class="text-[11px] sm:text-xs text-slate-500 italic">Bu döneme veya öncesine ait sisteme girilmiş laboratuvar tahlili kaydı bulunmuyor.</p>`;
            }
            labHtml += `</div></div>`;
            insight += labHtml;
            let medHtml = `<div><h4 class="text-xs sm:text-sm font-bold tracking-tight text-indigo-700 mb-2 flex items-center gap-2"><span class="h-2 w-2 sm:h-2.5 sm:w-2.5 rounded-full bg-teal-500 shadow-sm shadow-teal-200"></span> 4. İlaç Yönetimi: Uyum ve Tedavi Güncellemeleri</h4><div class="pl-3 sm:pl-4 border-l-2 border-slate-100 space-y-3">`;
            const oldStart = this.startDate;
            const oldEnd = this.endDate;
            this.startDate = startDate;
            this.endDate = endDate;
            this.calculateMetrics();
            const adherence = this.metrics.adherenceRate;
            this.startDate = oldStart;
            this.endDate = oldEnd;
            let adherenceComment =
                adherence >= 90
                    ? `<b>Tedaviye uyum oranınızın yüksek olması (%${adherence}), tüm kritik parametrelerinizin stabil kalmasındaki en büyük etkendir.</b> Cerrahi dikiş hatlarınızın korunması ve protez kapağın pıhtıya karşı savunulması açısından bu disiplin hayati önem taşımaktadır.`
                    : adherence >= 70
                      ? `İlaç uyumunuz genel olarak kabul edilebilir bir düzeyde (<b>%${adherence}</b>) ancak zaman zaman aksamalar tespit edilmiş. Tansiyon ve kan sulandırıcılarınızı saati saatine almaya azami özen göstermelisiniz.`
                      : `Maalesef ilaç uyumunuz <b>riskli derecede düşük (%${adherence})</b>. İlaçların aksatılması mekanik kapağınızın pıhtı tutmasına veya dikiş hatlarının hasar almasına zemin hazırlayabilir. Telefonunuza alarm kurmanızı tavsiye ederiz.`;
            let usedMedIds = new Set();
            let currentMedIds = new Set();
            this.medications.forEach((m) => {
                if (this.isMedicationActiveInRange(m.id)) usedMedIds.add(m.id);
                if (this.getMedicationStatusOnDate(m.id, endDate) === 'Active') currentMedIds.add(m.id);
            });
            let allChanges = getRecordsInRange(this.medicationChanges, startDate, endDate);
            allChanges.forEach((c) => {
                let med = this.medications.find((m) => m.id === c.medication_id);
                if (med && med.is_emergency && c.type === 'Taken') {
                    usedMedIds.add(med.id);
                }
            });
            const formatActiveDoseText = (med, amount, timespan) => {
                const baseDose = med.base_dose || 1;
                const pillCount = amount / baseDose;
                const formatPill = (c) => (c % 1 === 0 ? c : c.toFixed(2)).toString().replace('.50', '.5').replace('.00', '').replace('.0', '');
                let amtStr = `<b><span class="font-mono">${amount} ${med.unit}</span></b>`;
                let pillStr = `<i>${formatPill(pillCount)} adet</i>`;
                if (timespan === 168) return `haftalık toplam ${amtStr} (haftada toplam ${pillStr})`;
                if (timespan === 24) return `günde 1 kez ${amtStr} (${pillStr})`;
                if (timespan === 12) return `günde 2 kez ${amtStr} (her seferinde ${pillStr})`;
                if (timespan === 8) return `günde 3 kez ${amtStr} (her seferinde ${pillStr})`;
                if (timespan === 72) return `3 günde 1 kez ${amtStr} (${pillStr})`;
                return `${amtStr}`;
            };
            let activeDetails = [];
            currentMedIds.forEach((id) => {
                let med = this.medications.find((m) => m.id === id);
                if (!med) return;
                let latestChange = this.medicationChanges
                    .filter((c) => c.medication_id === id && c.at.substring(0, 10) <= endDate)
                    .sort((a, b) => a.at.localeCompare(b.at))
                    .pop();
                if (latestChange) {
                    activeDetails.push(`<b><i>${med.name}</i></b> ${formatActiveDoseText(med, latestChange.amount, latestChange.timespan)}`);
                } else {
                    activeDetails.push(`<b><i>${med.name}</i></b>`);
                }
            });
            let currentStr = activeDetails.length > 0 ? activeDetails.join(', ').replace(/, ([^,]*)$/, ' ve $1') : 'Yok';
            let additionalMedIds = Array.from(usedMedIds).filter((id) => !currentMedIds.has(id));
            let additionalMedNames = additionalMedIds.map((id) => `<b><i>${this.getMedicationName(id)}</i></b>`);
            let additionalStr = additionalMedNames.length > 0 ? additionalMedNames.join(', ').replace(/, ([^,]*)$/, ' ve $1') : '';
            let medicationSummaryText = `${adherenceComment}<br/><br/>İncelediğimiz dönemin sonu itibarıyla güncel tedavi şemanızda aktif olarak; ${currentStr} düzenli olarak kullanılmaktadır. `;
            if (additionalMedNames.length > 0) {
                medicationSummaryText += `Belirttiğiniz bu periyotta güncel listenize ek olarak <b>${additionalStr}</b> ilaçlarına da başvurulmuştur. `;
                let addNames = additionalMedIds.map((id) => this.getMedicationName(id));
                let infectMeds = addNames.filter((name) => ['Augmentin', 'Cipro', 'Tavanic', 'Stafine', 'Mikostatin'].includes(name));
                let painMeds = addNames.filter((name) => ['GeralginePlus'].includes(name));
                let vitaminMeds = addNames.filter((name) => ['Apikobal'].includes(name));
                let arrhythmiaMeds = addNames.filter((name) => ['Cordarone'].includes(name));
                let coughMeds = addNames.filter((name) => ['Levopront'].includes(name));
                if (infectMeds.length > 0) {
                    let fInfect = infectMeds
                        .map((n) => `<b><i>${n}</i></b>`)
                        .join(', ')
                        .replace(/, ([^,]*)$/, ' ve $1');
                    medicationSummaryText += `Bu dönemde ${fInfect} gibi koruyucu veya aktif enfeksiyon tedavilerinin kullanılması, vücudunuzda gelişebilecek fungal ve/veya bakteriyel bir enfeksiyon riskiyle mücadele edildiğini göstermektedir. `;
                }
                if (painMeds.length > 0) {
                    medicationSummaryText += `Ağrı kesici niteliğindeki <b><i>GeralginePlus</i></b> kullanımı, bu nekahat sürecinde semptomatik ağrı kontrolü ihtiyacınızın olduğunu ortaya koyuyor. `;
                }
                if (vitaminMeds.length > 0) {
                    medicationSummaryText += `B vitamini kompleksi olan <b><i>Apikobal</i></b> desteği ile ameliyat sonrası kemik (sternum) kaynamasının ve sinir sistemi toparlanmasının hızlandırılması amaçlanmıştır. `;
                }
                if (arrhythmiaMeds.length > 0) {
                    medicationSummaryText += `Ritim düzenleyici <b><i>Cordarone</i></b> tedavisi, açık kalp cerrahileri sonrasında sıkça tetiklenebilen ritim bozukluklarını (atriyal fibrilasyon vb.) kontrol altına almaya yöneliktir. `;
                }
                if (coughMeds.length > 0) {
                    medicationSummaryText += `Öksürük refleksini baskılayan <b><i>Levopront</i></b> ise göğüs dikişlerinizi sarsıntılardan korumak ve akciğer konforunuzu sağlamak için tedaviye eklenmiş. `;
                }
            }
            let emergencyMeds = this.medications.filter((m) => m.is_emergency).map((m) => m.name.toLowerCase());
            let emergencyLogs = this.medicationLogs.filter((l) => emergencyMeds.includes(l.med.toLowerCase()) && l.at.substring(0, 10) >= startDate && l.at.substring(0, 10) <= endDate).sort((a, b) => a.at.localeCompare(b.at));
            if (emergencyLogs.length > 0) {
                let emergencyInsights = [];
                emergencyLogs.forEach((logItem, index) => {
                    let changeDate = logItem.at.substring(0, 10);
                    let intakeTime = logItem.at.substring(11, 16);
                    let intakeMs = new Date(logItem.at.replace(' ', 'T')).getTime();
                    let dayPressures = this.pressures.filter((p) => p.at.substring(0, 10) === changeDate).sort((a, b) => a.at.localeCompare(b.at));
                    let windowPressures = dayPressures.filter((p) => {
                        let pMs = new Date(p.at.replace(' ', 'T')).getTime();
                        let diffMin = (pMs - intakeMs) / 60000;
                        return diffMin >= -60 && diffMin <= 240;
                    });
                    let prePressures = windowPressures.filter((p) => p.at <= logItem.at);
                    let postPressures = windowPressures.filter((p) => p.at > logItem.at);
                    let nextIntake = emergencyLogs.find((li) => li.at > logItem.at && li.at.substring(0, 10) === changeDate && li.med === logItem.med);
                    if (nextIntake) {
                        postPressures = postPressures.filter((p) => p.at < nextIntake.at);
                    }
                    let dateFormatted = formatDateNatural(changeDate);
                    let medName = `<b><i>${logItem.med}</i></b>`;
                    if (prePressures.length > 0) {
                        let preTxtList = prePressures
                            .map((p) => {
                                let tStr = p.at.substring(11, 16);
                                return `saat <span class="font-mono font-bold">${tStr}</span>'da <span class="font-mono font-bold">${p.sys}/${p.dia} mmHg</span>`;
                            })
                            .join(' ve ');
                        let postTxt = '';
                        let evaluationTxt = '';
                        if (postPressures.length > 0) {
                            let postTxtList = postPressures
                                .map((p) => {
                                    let tStr = p.at.substring(11, 16);
                                    return `saat <span class="font-mono font-bold">${tStr}</span>'da <span class="font-mono font-bold">${p.sys}/${p.dia} mmHg</span>`;
                                })
                                .join(' ve ');
                            postTxt = ` Takip ölçümleri ise ${postTxtList} olarak yapılmıştır.`;
                            let lastPost = postPressures[postPressures.length - 1];
                            let peakSys = Math.max(...windowPressures.map((p) => p.sys));
                            if (lastPost.sys < 130 && lastPost.dia < 85) {
                                evaluationTxt = ` <span class="text-emerald-700 font-semibold">Tansiyonun en son takip ölçümünde ${lastPost.sys}/${lastPost.dia} mmHg seviyesine inmesi, yapılan acil müdahalenin başarıyla sonuçlandığını ve ilacın işe yaradığını göstermektedir.</span>`;
                            } else if (lastPost.sys < peakSys - 15) {
                                evaluationTxt = ` <span class="text-emerald-600">Tansiyon pik değeri olan ${peakSys} mmHg'den takipte ${lastPost.sys}/${lastPost.dia} mmHg seviyesine gerilemiştir; ilaç tansiyonu düşürmekte işe yaramış ancak tam stabilizasyon için yakın takip gerekmektedir.</span>`;
                            } else {
                                evaluationTxt = ` <span class="text-rose-600 font-semibold">Tansiyonun takip ölçümlerinde halen ${lastPost.sys}/${lastPost.dia} mmHg seviyesinde yüksek seyretmesi, acil müdahalenin yetersiz kalmış olabileceğini veya ek bir tıbbi değerlendirme gerektirdiğini göstermektedir.</span>`;
                            }
                        } else {
                            postTxt = ` Ancak ilacın hemen sonrasına ait takip ölçümü sistemde bulunmamaktadır.`;
                            evaluationTxt = ` <span class="text-slate-500 italic">Takip ölçümü girilmediği için ilacın klinik etkisi tam olarak değerlendirilememiştir.</span>`;
                        }
                        emergencyInsights.push(`<span class="font-mono font-bold">${dateFormatted}</span> günü, ${preTxtList} yüksek tansiyon ölçümlerini takiben saat <span class="font-mono font-bold">${intakeTime}</span>'de acil durum ilacı olarak ${medName} kullanılmıştır.${postTxt}${evaluationTxt}`);
                    } else {
                        emergencyInsights.push(`<span class="font-mono font-bold">${dateFormatted} saat ${intakeTime}</span>'de acil durum ilacı olarak ${medName} kullanılmıştır. <span class="text-slate-400 italic">(Bu uygulamanın 1 saat öncesine ait bir tansiyon ölçüm kaydı bulunmadığından kıyaslama yapılamamıştır.)</span>`);
                    }
                });
                medicationSummaryText += `<div class="mt-3 p-3 bg-rose-50 border border-rose-200 rounded-lg shadow-sm"><span class="font-bold text-xs flex items-center gap-1.5 text-rose-800 mb-1.5">⚠️ Acil Durum İlacı Kullanım Raporu:</span>`;
                emergencyInsights.forEach((ins) => {
                    medicationSummaryText += `<p class="text-[11px] sm:text-xs leading-relaxed font-medium mt-1">&bull; ${ins}</p>`;
                });
                medicationSummaryText += `</div>`;
            }
            medHtml += `<p class="text-[11px] sm:text-xs text-slate-700 leading-relaxed">${medicationSummaryText}</p>`;
            const formatDoseList = (med, amount, timespan) => {
                const baseDose = med.base_dose || 1;
                const pillCount = amount / baseDose;
                const formatPill = (c) => (c % 1 === 0 ? c : c.toFixed(2)).toString().replace('.50', '.5').replace('.00', '').replace('.0', '');
                let amtStr = `<span class="font-mono font-bold">${amount} ${med.unit}</span>`;
                let pillStr = `(<span class="font-mono font-bold">${formatPill(pillCount)}</span> adet)`;
                if (timespan === 168) return `<i>haftalık toplam</i> ${amtStr} ${pillStr}`;
                if (timespan === 24) return `<i>günde 1 kez</i> ${amtStr} ${pillStr}`;
                if (timespan === 12) return `<i>günde 2 kez</i> ${amtStr} ${pillStr}`;
                if (timespan === 8) return `<i>günde 3 kez</i> ${amtStr} ${pillStr}`;
                if (timespan === 72) return `<i>3 günde 1 kez</i> ${amtStr} ${pillStr}`;
                return `${amtStr}`;
            };
            if (allChanges.length > 0) {
                medHtml += `<h5 class="text-[11px] sm:text-xs font-extrabold text-slate-800 uppercase tracking-wide mt-3 mb-1">Dönem İçi Tedavi Değişiklik Kronolojisi</h5><ul class="space-y-2 list-disc pl-4 text-[11px] sm:text-xs text-slate-700 leading-relaxed">`;
                let changedMeds = [];
                this.medications.forEach((med) => {
                    let mChanges = allChanges.filter((c) => c.medication_id === med.id);
                    if (mChanges.length > 0) {
                        let latestDate = mChanges[mChanges.length - 1].at;
                        changedMeds.push({ med, mChanges, latestDate });
                    }
                });
                changedMeds.sort((a, b) => b.latestDate.localeCompare(a.latestDate));
                let hasChangeOutput = false;
                changedMeds.forEach(({ med, mChanges }) => {
                    let prev = this.medicationChanges
                        .filter((c) => c.medication_id === med.id && c.at.substring(0, 10) < startDate)
                        .sort((a, b) => a.at.localeCompare(b.at))
                        .pop();
                    let strParts = [];
                    let takenCounts = {};
                    for (let i = 0; i < mChanges.length; i++) {
                        let c = mChanges[i];
                        if (c.processed) continue;
                        let dateStr = `<span class="font-mono">${formatDateNatural(c.at)}</span>`;
                        if (c.type === 'Taken') {
                            let dKey = c.at.substring(0, 10);
                            if (!takenCounts[dKey]) takenCounts[dKey] = [];
                            takenCounts[dKey].push(c);
                            continue;
                        }
                        if (c.type === 'Started' || c.type === 'Resumed') {
                            let nextEndIdx = mChanges.findIndex((mc, idx) => idx > i && (mc.type === 'Ended' || mc.type === 'Paused'));
                            let nextChangeIdx = mChanges.findIndex((mc, idx) => idx > i && mc.type === 'Changed');
                            if (nextEndIdx !== -1 && (nextChangeIdx === -1 || nextEndIdx < nextChangeIdx)) {
                                let endC = mChanges[nextEndIdx];
                                let endStr = `<span class="font-mono">${formatDateNatural(endC.at)}</span>`;
                                strParts.push(`${dateStr} ile ${endStr} arasında ${formatDoseList(med, c.amount, c.timespan)} kullanıldı.`);
                                mChanges[nextEndIdx].processed = true;
                            } else {
                                strParts.push(`${dateStr} tarihinde ${formatDoseList(med, c.amount, c.timespan)} dozajıyla başlandı.`);
                            }
                        } else if (c.type === 'Changed') {
                            let oldDose = prev ? formatDoseList(med, prev.amount, prev.timespan) : 'eski dozu';
                            strParts.push(`${dateStr} tarihinde dozu ${oldDose} iken ${formatDoseList(med, c.amount, c.timespan)} olarak değiştirildi.`);
                        } else if (c.type === 'Ended' || c.type === 'Paused') {
                            strParts.push(`${dateStr} tarihinde kullanımı sonlandırıldı.`);
                        }
                        prev = c;
                    }
                    for (let dKey in takenCounts) {
                        let takes = takenCounts[dKey];
                        let dateStr = `<span class="font-mono">${formatDateNatural(dKey)}</span>`;
                        let amountStr = `<span class="font-mono font-bold">${takes[0].amount} ${med.unit}</span>`;
                        if (takes.length > 1) {
                            strParts.push(`${dateStr} tarihinde ${takes.length} kez tek seferlik acil durum dozu ${amountStr} olarak uygulandı.`);
                        } else {
                            strParts.push(`${dateStr} tarihinde tek seferlik acil durum dozu ${amountStr} olarak uygulandı.`);
                        }
                    }
                    if (strParts.length > 0) {
                        hasChangeOutput = true;
                        medHtml += `<li><b><i>${med.name}</i>:</b> ${strParts.join(' ')}</li>`;
                    }
                });
                if (!hasChangeOutput) {
                    medHtml += `<li>Sıradışı bir kayıt veya doz değişimi tespit edilemedi.</li>`;
                }
                medHtml += `</ul>`;
            } else {
                medHtml += `<p class="text-[11px] sm:text-xs text-slate-500 italic mt-2">Bu dönem içerisinde ilaç listenizde herhangi bir ekleme, çıkarma veya doz değişimi yapılmamış, mevcut tedavinize aynı şekilde devam edilmiştir.</p>`;
            }
            medHtml += `</div></div>`;
            insight += medHtml;
            return insight;
        },
        getInsightPeriods(baseEnd, baseStart, excludePreset = null) {
            const end = new Date(baseEnd);
            const start = new Date(baseStart);
            const periods = [];
            const addPeriod = (label, startDate, endDate) => {
                if (excludePreset && label === excludePreset) return;
                if (startDate > endDate) return;
                if (startDate < new Date(baseStart)) return;
                periods.push({
                    label: label,
                    start: startDate.toISOString().split('T')[0],
                    end: endDate.toISOString().split('T')[0],
                });
            };
            addPeriod('all', start, end);
            const presets = [
                { label: 'last3', days: 3 },
                { label: 'last7', days: 7 },
                { label: 'last10', days: 10 },
                { label: 'last15', days: 15 },
                { label: 'last30', days: 30 },
                { label: 'last45', days: 45 },
                { label: 'last60', days: 60 },
                { label: 'last90', days: 90 },
            ];
            presets.forEach(({ label, days }) => {
                let dStart = new Date(end);
                dStart.setDate(dStart.getDate() - (days - 1));
                addPeriod(label, dStart, end);
            });
            return periods;
        },
        destroyAllCharts() {
            if (window.clinicalCharts) {
                Object.keys(window.clinicalCharts).forEach((key) => {
                    if (window.clinicalCharts[key] && typeof window.clinicalCharts[key].destroy === 'function') {
                        try {
                            window.clinicalCharts[key].destroy();
                        } catch (e) {}
                    }
                    window.clinicalCharts[key] = null;
                });
            }
        },
        renderMainCharts() {
            const self = this;

            const formatDateToDDMM = (dateStr) => {
                if (!dateStr) return '';
                const parts = dateStr.split(' ');
                const datePart = parts[0];
                const timePart = parts[1];
                const dateArr = datePart.split('-');
                if (dateArr.length === 3) {
                    let formatted = dateArr[2] + '.' + dateArr[1];
                    if (timePart) {
                        formatted += ' ' + timePart.slice(0, 5);
                    }
                    return formatted;
                }
                return dateStr;
            };

            if (window.clinicalCharts && window.clinicalCharts['bp']) {
                try {
                    window.clinicalCharts['bp'].destroy();
                } catch (e) {}
                window.clinicalCharts['bp'] = null;
            }
            if (window.clinicalCharts && window.clinicalCharts['weight']) {
                try {
                    window.clinicalCharts['weight'].destroy();
                } catch (e) {}
                window.clinicalCharts['weight'] = null;
            }

            let fps = [...this.getFilteredPressures()].sort((a, b) => new Date(a.at) - new Date(b.at));
            let bpCtx = document.getElementById('bpLineChart')?.getContext('2d');
            if (bpCtx && fps.length > 0) {
                let chartData = [];

                if (this.bpViewMode === 'trend') {
                    const start = new Date(this.startDate);
                    const end = new Date(this.endDate);
                    let daysCount = Math.round((end - start) / (24 * 60 * 60 * 1000));
                    for (let i = 0; i <= daysCount; i++) {
                        let current = new Date(start);
                        current.setDate(current.getDate() + i);
                        let currentIsoDate = current.toISOString().split('T')[0];
                        let targetEnd = new Date(currentIsoDate);
                        let targetStart = new Date(currentIsoDate);
                        targetStart.setDate(targetStart.getDate() - 6);

                        let readingsInWindow = this.pressures.filter((p) => {
                            let pDate = new Date(p.at.substring(0, 10));
                            return pDate >= targetStart && pDate <= targetEnd;
                        });

                        let dateObj = new Date(currentIsoDate + 'T00:00:00');

                        if (readingsInWindow.length > 0) {
                            let avgSys = readingsInWindow.reduce((sum, p) => sum + p.sys, 0) / readingsInWindow.length;
                            let avgDia = readingsInWindow.reduce((sum, p) => sum + p.dia, 0) / readingsInWindow.length;
                            chartData.push({ x: dateObj, sys: Math.round(avgSys), dia: Math.round(avgDia) });
                        } else {
                            if (this.pressures.some((p) => p.at.substring(0, 10) === currentIsoDate)) {
                                chartData.push({ x: dateObj, sys: null, dia: null });
                            }
                        }
                    }
                } else {
                    chartData = fps.map((p) => ({
                        x: new Date(p.at),
                        sys: p.sys,
                        dia: p.dia,
                    }));
                }

                let sysData = chartData.map((d) => ({ x: d.x, y: d.sys }));
                let diaData = chartData.map((d) => ({ x: d.x, y: d.dia }));

                let allVals = chartData.flatMap((d) => [d.sys, d.dia]).filter((v) => v !== null && !isNaN(v));
                let bpMin = allVals.length > 0 ? Math.max(0, Math.floor(Math.min(...allVals) - 10)) : 50;
                let bpMax = allVals.length > 0 ? Math.ceil(Math.max(...allVals) + 10) : 170;

                if (this.bpViewMode === 'trend') {
                    bpMin = 70;
                    bpMax = 130;
                } else {
                    bpMin = 50;
                    bpMax = 170;
                }

                window.clinicalCharts['bp'] = new Chart(bpCtx, {
                    type: 'line',
                    data: {
                        datasets: [
                            {
                                label: 'Sistolik',
                                data: sysData,
                                borderColor: 'rgb(225, 29, 72)',
                                backgroundColor: 'rgba(225, 29, 72, 0.03)',
                                pointRadius: 1,
                                borderWidth: 2,
                                tension: 0.2,
                                fill: true,
                                spanGaps: true,
                            },
                            {
                                label: 'Diastolik',
                                data: diaData,
                                borderColor: 'rgb(79, 70, 229)',
                                backgroundColor: 'rgba(79, 70, 229, 0.03)',
                                pointRadius: 1,
                                borderWidth: 2,
                                tension: 0.2,
                                fill: false,
                                spanGaps: true,
                            },
                        ],
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        animation: false,
                        interaction: { mode: 'index', intersect: false },
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                callbacks: {
                                    title: function (tooltipItems) {
                                        const date = new Date(tooltipItems[0].parsed.x);
                                        return self.formatFullDate(date);
                                    },
                                },
                            },
                        },
                        scales: {
                            x: {
                                type: 'time',
                                time: {
                                    unit: 'day',
                                    displayFormats: { day: 'D MMM' },
                                },
                                grid: { display: false },
                                ticks: {
                                    callback: function (value) {
                                        const date = new Date(value);
                                        const months = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara'];
                                        return date.getDate() + ' ' + months[date.getMonth()];
                                    },
                                },
                            },
                            y: {
                                ticks: { stepSize: 10 },
                                min: bpMin,
                                max: bpMax,
                                grid: { color: 'rgba(226, 232, 240, 0.6)' },
                            },
                        },
                    },
                });
            }

            let fws = [...this.getFilteredWeights()].sort((a, b) => new Date(a.at) - new Date(b.at));
            let wCtx = document.getElementById('weightLineChart')?.getContext('2d');
            if (wCtx && fws.length > 0) {
                let weightData = fws.map((w) => ({ x: new Date(w.at), y: w.weight }));
                let weightsPool = weightData.map((d) => d.y);
                let minW = Math.max(0, Math.floor(Math.min(...weightsPool) - 2));
                let maxW = Math.ceil(Math.max(...weightsPool) + 2);

                window.clinicalCharts['weight'] = new Chart(wCtx, {
                    type: 'line',
                    data: {
                        datasets: [
                            {
                                label: 'Kilo (kg)',
                                data: weightData,
                                borderColor: 'rgb(13, 148, 136)',
                                backgroundColor: 'rgba(13, 148, 136, 0.03)',
                                pointRadius: 1,
                                borderWidth: 2,
                                tension: 0.2,
                                fill: true,
                            },
                        ],
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        animation: false,
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                callbacks: {
                                    title: function (tooltipItems) {
                                        const date = new Date(tooltipItems[0].parsed.x);
                                        return self.formatFullDate(date);
                                    },
                                },
                            },
                        },
                        scales: {
                            x: {
                                type: 'time',
                                time: { unit: 'day', displayFormats: { day: 'D MMM' } },
                                grid: { display: false },
                                ticks: {
                                    callback: function (value) {
                                        const date = new Date(value);
                                        const months = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara'];
                                        return date.getDate() + ' ' + months[date.getMonth()];
                                    },
                                },
                            },
                            y: {
                                min: minW,
                                max: maxW,
                                grid: { color: 'rgba(226, 232, 240, 0.6)' },
                            },
                        },
                    },
                });
            }
        },
        renderFocusChart() {
            if (this.flowsheetMode !== 'chart') return;
            if (window.clinicalCharts && window.clinicalCharts['focus']) {
                try {
                    window.clinicalCharts['focus'].destroy();
                } catch (e) {}
                window.clinicalCharts['focus'] = null;
            }
            let canvas = document.getElementById('focusChartCanvas');
            if (!canvas) return;

            // Hangi ilaçları göstereceğimizi belirle
            let medsToShow = this.selectedMed.length > 0 ? this.selectedMed : this.allFlowsheetMeds;
            if (medsToShow.length === 0) {
                // hiç ilaç yoksa grafik boş
                return;
            }

            const self = this;
            let start = new Date(this.startDate);
            let end = new Date(this.endDate);
            let daysCount = Math.round((end - start) / (24 * 60 * 60 * 1000));
            let daysKeys = [];
            const months = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara'];

            for (let i = 0; i <= daysCount; i++) {
                let temp = new Date(start);
                temp.setDate(temp.getDate() + i);
                let iso = temp.toISOString().split('T')[0];
                daysKeys.push(new Date(iso + 'T00:00:00'));
            }

            let datasets = [];
            medsToShow.forEach((medName) => {
                let cfg = this.medConfig[medName] || { color: 'rgb(100, 116, 139)' };
                let values = daysKeys.map((date) => {
                    let iso = date.toISOString().split('T')[0];
                    let dayLogs = this.medicationLogs.filter((l) => l.med.toLowerCase() === medName.toLowerCase() && l.at.substring(0, 10) === iso);
                    let base_dose = this.medConversions[medName] || 1;
                    let totalDose = dayLogs.reduce((sum, l) => sum + l.dose, 0);
                    return totalDose / base_dose;
                });

                let data = daysKeys.map((date, idx) => ({ x: date, y: values[idx] }));

                datasets.push({
                    label: medName,
                    data: data,
                    backgroundColor: cfg.color,
                    borderColor: cfg.color,
                    borderRadius: 4,
                    borderWidth: 1,
                });
            });

            window.clinicalCharts['focus'] = new Chart(canvas.getContext('2d'), {
                type: 'bar',
                data: { datasets: datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: false,
                    plugins: {
                        tooltip: {
                            callbacks: {
                                title: function (tooltipItems) {
                                    const date = new Date(tooltipItems[0].parsed.x);
                                    return self.formatFullDate(date);
                                },
                            },
                        },
                    },
                    scales: {
                        x: {
                            type: 'time',
                            time: {
                                unit: 'day',
                                displayFormats: { day: 'D MMM' },
                            },
                            grid: { display: false },
                            border: { display: false },
                            ticks: {
                                callback: function (value) {
                                    const date = new Date(value);
                                    return date.getDate() + ' ' + months[date.getMonth()];
                                },
                            },
                        },
                        y: {
                            beginAtZero: true,
                            grid: { color: 'rgba(226, 232, 240, 0.6)' },
                            border: { display: false },
                        },
                    },
                },
            });
        },
        renderLabTrendCharts() {
            const targets = [
                { id: 'inrLabChart', code: 'INR', label: 'INR', color: 'rgb(249, 115, 22)' },
                { id: 'ptChart', code: 'PT', label: 'PT (sn)', color: 'rgb(217, 119, 6)' },
                { id: 'apttChart', code: 'APTT', label: 'aPTT (sn)', color: 'rgb(234, 179, 8)' },
                { id: 'hgbChart', code: 'HGB', label: 'HGB', color: 'rgb(185, 28, 28)' },
                { id: 'hctChart', code: 'HCT', label: 'HCT', color: 'rgb(239, 68, 68)' },
                { id: 'rbcChart', code: 'RBC', label: 'RBC', color: 'rgb(244, 63, 94)' },
                { id: 'pltChart', code: 'PLT', label: 'PLT', color: 'rgb(16, 185, 129)' },
                { id: 'wbcChart', code: 'WBC', label: 'WBC', color: 'rgb(79, 70, 229)' },
                { id: 'crpChart', code: 'CRP', label: 'CRP', color: 'rgb(236, 72, 153)' },
                { id: 'lymChart', code: 'LYM', label: 'Lenfosit', color: 'rgb(148, 163, 184)' },
                { id: 'neuChart', code: 'NEU', label: 'NEU', color: 'rgb(139, 92, 246)' },
                { id: 'creaChart', code: 'CREA', label: 'CREA', color: 'rgb(20, 184, 166)' },
                { id: 'bunChart', code: 'BUN', label: 'BUN', color: 'rgb(6, 182, 212)' },
                { id: 'altChart', code: 'ALT', label: 'ALT', color: 'rgb(163, 230, 53)' },
                { id: 'gluChart', code: 'GLU', label: 'GLU', color: 'rgb(217, 70, 239)' },
                { id: 'naChart', code: 'NA', label: 'Sodyum', color: 'rgb(14, 165, 233)' },
                { id: 'kChart', code: 'K', label: 'Potasyum', color: 'rgb(225, 29, 72)' },
                { id: 'caChart', code: 'CA', label: 'Kalsiyum', color: 'rgb(245, 158, 11)' },
            ];

            const self = this;
            const months = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara'];

            targets.forEach((tgt) => {
                if (window.clinicalCharts && window.clinicalCharts[tgt.id]) {
                    try {
                        window.clinicalCharts[tgt.id].destroy();
                    } catch (e) {}
                    window.clinicalCharts[tgt.id] = null;
                }
                let canvasEl = document.getElementById(tgt.id);
                if (!canvasEl) return;

                let allPoints = [];
                this.tests.forEach((s) => {
                    let match = this.testItems.find((item) => {
                        if (item.test_id !== s.id) return false;
                        let itemCode = item.code.toUpperCase();
                        return itemCode === tgt.code || (tgt.code === 'NEU' && itemCode === 'NEU#') || (tgt.code === 'LYM' && itemCode === 'LYM#') || (tgt.code === 'NA' && itemCode === 'SODYUM') || (tgt.code === 'K' && itemCode === 'POTASYUM') || (tgt.code === 'CA' && (itemCode === 'KALSİYUM' || itemCode === 'KALSIYUM'));
                    });
                    if (match) {
                        allPoints.push({
                            val: parseFloat(match.result),
                            date: s.at.substring(0, 10),
                            rawDate: s.at,
                            refMin: match.reference_min ? parseFloat(match.reference_min) : null,
                            refMax: match.reference_max ? parseFloat(match.reference_max) : null,
                        });
                    }
                });

                allPoints.sort((a, b) => new Date(a.rawDate) - new Date(b.rawDate));

                let insideRange = allPoints.filter((p) => p.date >= this.startDate && p.date <= this.endDate);
                let beforeRange = allPoints.filter((p) => p.date < this.startDate);

                let finalPoints = [];
                if (insideRange.length >= 2) {
                    if (beforeRange.length > 0) finalPoints.push(beforeRange[beforeRange.length - 1]);
                    finalPoints = finalPoints.concat(insideRange);
                } else if (insideRange.length === 1) {
                    finalPoints = [...insideRange];
                    let idx = beforeRange.length - 1;
                    while (finalPoints.length < 2 && idx >= 0) {
                        finalPoints.unshift(beforeRange[idx]);
                        idx--;
                    }
                } else {
                    let idx = beforeRange.length - 1;
                    while (finalPoints.length < 2 && idx >= 0) {
                        finalPoints.unshift(beforeRange[idx]);
                        idx--;
                    }
                }

                if (finalPoints.length === 0) return;

                let dData = finalPoints.map((p) => ({ x: new Date(p.rawDate), y: p.val }));
                let minData = finalPoints.map((p) => ({ x: new Date(p.rawDate), y: p.refMin }));
                let maxData = finalPoints.map((p) => ({ x: new Date(p.rawDate), y: p.refMax }));

                let ctx = canvasEl.getContext('2d');
                window.clinicalCharts[tgt.id] = new Chart(ctx, {
                    type: 'line',
                    data: {
                        datasets: [
                            {
                                label: 'Max Sınır',
                                data: maxData,
                                borderColor: 'rgba(34, 197, 94, 0.15)',
                                borderWidth: 1,
                                borderDash: [2, 2],
                                pointRadius: 0,
                                tension: 0,
                                fill: false,
                                spanGaps: true,
                            },
                            {
                                label: 'Min Sınır',
                                data: minData,
                                borderColor: 'rgba(34, 197, 94, 0.15)',
                                borderWidth: 1,
                                borderDash: [2, 2],
                                pointRadius: 0,
                                tension: 0,
                                fill: 0,
                                backgroundColor: 'rgba(34, 197, 94, 0.02)',
                                spanGaps: true,
                            },
                            {
                                label: tgt.label,
                                data: dData,
                                borderColor: tgt.color,
                                backgroundColor: tgt.color.replace('rgb', 'rgba').replace(')', ',0.03)'),
                                borderWidth: 1.5,
                                pointRadius: 2.5,
                                tension: 0.15,
                                fill: false,
                                spanGaps: true,
                            },
                        ],
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        animation: false,
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                callbacks: {
                                    title: function (tooltipItems) {
                                        const date = new Date(tooltipItems[0].parsed.x);
                                        return self.formatFullDate(date);
                                    },
                                    label: function (context) {
                                        if (context.datasetIndex === 2) {
                                            return `${context.dataset.label}: ${context.raw.y}`;
                                        }
                                        return null;
                                    },
                                },
                            },
                        },
                        scales: {
                            x: {
                                type: 'time',
                                time: {
                                    unit: 'day',
                                    displayFormats: { day: 'D MMM' },
                                },
                                grid: { display: false },
                                ticks: {
                                    font: { size: 8 },
                                    callback: function (value) {
                                        const date = new Date(value);
                                        return date.getDate() + ' ' + months[date.getMonth()];
                                    },
                                },
                            },
                            y: {
                                grid: { color: 'rgba(226, 232, 240, 0.4)' },
                                ticks: { font: { size: 8 } },
                            },
                        },
                    },
                });
            });
        },

        getLabItemStatus(item) {
            if (!item.reference_min || !item.reference_max) return 'Normal';
            let val = parseFloat(item.result);
            if (val < parseFloat(item.reference_min)) return 'Düşük';
            if (val > parseFloat(item.reference_max)) return 'Yüksek';
            return 'Normal';
        },
        getLabItemClass(item) {
            let s = this.getLabItemStatus(item);
            if (s === 'Yüksek') return 'text-rose-600';
            if (s === 'Düşük') return 'text-amber-600';
            return 'text-emerald-600';
        },
        getLabPointerClass(item) {
            let s = this.getLabItemStatus(item);
            if (s === 'Yüksek') return 'bg-rose-500 ring-4 ring-rose-100';
            if (s === 'Düşük') return 'bg-amber-500 ring-4 ring-amber-100';
            return 'bg-emerald-500 ring-4 ring-emerald-100';
        },
        getRangeZoneStyle(item) {
            if (!item.reference_min || !item.reference_max) return 'left: 0%; width: 100%;';
            let min = parseFloat(item.reference_min);
            let max = parseFloat(item.reference_max);
            let span = max * 1.4;
            let left = Math.min((min / span) * 100, 75);
            let width = Math.min(((max - min) / span) * 100, 95 - left);
            return `left: ${left.toFixed(1)}%; width: ${width.toFixed(1)}%;`;
        },
        getPointerPositionStyle(item) {
            let val = parseFloat(item.result);
            if (!item.reference_max) return 'left: 50%;';
            let max = parseFloat(item.reference_max);
            let span = max * 1.4;
            let pct = Math.min((val / span) * 100, 96);
            return `left: ${pct.toFixed(1)}%;`;
        },
        calculateIndividualWeightDiff(wObj) {
            let sorted = [...this.weights].sort((a, b) => new Date(a.at) - new Date(b.at));
            let idx = sorted.findIndex((item) => item.at === wObj.at);
            if (idx <= 0) return '-';
            let diff = (wObj.weight - sorted[idx - 1].weight).toFixed(1);
            return diff >= 0 ? `+${diff} kg` : `${diff} kg`;
        },
        getWeightDiffClass(wObj) {
            let sorted = [...this.weights].sort((a, b) => new Date(a.at) - new Date(b.at));
            let idx = sorted.findIndex((item) => item.at === wObj.at);
            if (idx <= 0) return 'text-slate-400';
            return wObj.weight - sorted[idx - 1].weight > 0 ? 'bg-amber-50 text-amber-700 border border-amber-200' : 'bg-emerald-50 text-emerald-700 border border-emerald-200';
        },
        getBPStatusText(sys, dia) {
            if (sys >= 140 || dia >= 90) return 'Hipertansiyon';
            if (sys >= 130 || dia >= 85) return 'Prehipertansiyon';
            return 'Normal';
        },
        getBPBadgeClass(sys, dia) {
            let s = this.getBPStatusText(sys, dia);
            if (s === 'Hipertansiyon') return 'bg-rose-50 text-rose-700 border border-rose-200';
            if (s === 'Prehipertansiyon') return 'bg-amber-50 text-amber-700 border border-amber-200';
            return 'bg-emerald-50 text-emerald-700 border border-emerald-200';
        },
        updateFilters() {
            let todayStr = new Date().toISOString().split('T')[0];
            if (!this.startDate) this.startDate = this.firstD;
            if (!this.endDate) this.endDate = this.lastD;
            this.startDate = this.snapDateToValid(this.startDate);
            this.endDate = this.snapDateToValid(this.endDate);
            if (this.startDate < this.firstD) this.startDate = this.firstD;
            if (this.endDate > this.lastD) this.endDate = this.lastD;
            if (this.endDate > todayStr) this.endDate = todayStr;
            if (this.startDate > this.endDate) {
                this.startDate = this.endDate;
            }
            if (this.endDate < this.startDate) {
                this.endDate = this.startDate;
            }
            if (this.endDate) {
                let parts = this.endDate.split('-');
                this.calendarYear = parseInt(parts[0]);
                this.calendarMonth = parseInt(parts[1]) - 1;
                this.selectedCalendarDayStr = this.endDate;
            }
            this.calculateMetrics();
            this.updateVisibleMeds();
            this.setupFlowsheet();
            this.$nextTick(() => {
                this.renderMainCharts();
                this.renderLabTrendCharts();
                if (this.flowsheetMode === 'chart') {
                    this.renderFocusChart();
                }
            });
        },
        applyDatePreset() {
            const mode = this.datePreset;
            if (mode === 'custom') return;
            this.previousStartDate = null;
            this.endDate = this.lastD;
            let dateObj = new Date(this.lastD);
            if (mode === 'all') {
                this.startDate = this.firstD;
            } else {
                const days = parseInt(mode, 10);
                if (!isNaN(days) && days > 0) {
                    dateObj.setDate(dateObj.getDate() - (days - 1));
                    this.startDate = dateObj.toISOString().split('T')[0];
                } else {
                    this.startDate = this.firstD;
                }
            }
            this.updateFilters();
        },
        shiftDatePeriod(direction) {
            if (this.datePreset === 'all') return;
            let start = new Date(this.startDate);
            let end = new Date(this.endDate);
            let diffDays = Math.round((end - start) / (24 * 60 * 60 * 1000));
            if (diffDays === 0) diffDays = 1;
            let newStart = new Date(start);
            let newEnd = new Date(end);
            if (direction === -1) {
                newStart.setDate(start.getDate() - diffDays);
                newEnd.setDate(end.getDate() - diffDays);
            } else if (direction === 1) {
                newStart.setDate(start.getDate() + diffDays);
                newEnd.setDate(end.getDate() + diffDays);
                let lastDObj = new Date(this.lastD);
                if (newEnd > lastDObj) {
                    let overflow = Math.round((newEnd - lastDObj) / (24 * 60 * 60 * 1000));
                    newEnd = lastDObj;
                    newStart.setDate(newStart.getDate() - overflow);
                }
            }
            this.startDate = newStart.toISOString().split('T')[0];
            this.endDate = newEnd.toISOString().split('T')[0];
            this.datePreset = 'custom';
            this.updateFilters();
        },
        selectLabSession(id) {
            this.selectedTestId = id;
            this.selectedTestObj = this.tests.find((t) => t.id === id) || {};
            this.selectedTestItems = this.testItems.filter((item) => item.test_id === id);
        },
        getHospitalName(id) {
            return this.hospitals.find((h) => h.id === id)?.name || 'Klinik Kurumu';
        },
        getMedicationName(id) {
            return this.medications.find((m) => m.id === id)?.name || 'İlaç';
        },
        getMedicationUnit(id) {
            return this.medications.find((m) => m.id === id)?.unit || 'mg';
        },
        getMedicationUnitByName(name) {
            let match = this.medications.find((m) => m.name.toLowerCase() === name.toLowerCase());
            return match ? `${match.base_dose} ${match.unit}` : '';
        },
        getMedicationUnitOnlyByName(name) {
            let match = this.medications.find((m) => m.name.toLowerCase() === name.toLowerCase());
            return match ? match.unit : 'mg';
        },
        getTimelineBadgeClass(type) {
            if (type === 'Started') return 'bg-emerald-500 ring-emerald-100';
            if (type === 'Ended') return 'bg-rose-500 ring-rose-100';
            if (type === 'Paused') return 'bg-amber-500 ring-amber-100';
            return 'bg-indigo-500 ring-indigo-100';
        },
        getTimelineTextClass(type) {
            if (type === 'Started') return 'bg-emerald-50 text-emerald-700 border border-emerald-200';
            if (type === 'Ended') return 'bg-rose-50 text-rose-700 border border-rose-200';
            if (type === 'Paused') return 'bg-amber-50 text-amber-700 border border-amber-200';
            return 'bg-indigo-50 text-indigo-700 border border-indigo-200';
        },
        getTimelineActionLabel(type) {
            const dict = { Started: 'Başlatıldı', Changed: 'Doz Değişimi', Paused: 'Ara Verildi', Resumed: 'Yeniden Başladı', Ended: 'Sonlandırıldı', Taken: 'Uygulandı' };
            return dict[type] || type;
        },
        formatFlowsheetHeader(dayStr) {
            let d = new Date(dayStr);
            const days = ['Paz', 'Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt'];
            const months = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara'];
            return { dow: days[d.getDay()], date: `${d.getDate()} ${months[d.getMonth()]}` };
        },
        showTooltip(med, day, event) {
            let data = this.getMedLogForDay(med, day);
            if (data.count === 0) return;
            let bounds = event.target.getBoundingClientRect();
            this.tooltip.show = true;
            this.tooltip.med = med;
            this.tooltip.date = this.formatFullDate(day);
            this.tooltip.count = data.displayValue;
            this.tooltip.times = data.logs.map((l) => l.tooltipStr);
            let tooltipWidth = 200;
            let tooltipHeight = 130;
            let x = window.scrollX + bounds.left + bounds.width / 2 - tooltipWidth / 2;
            let y = window.scrollY + bounds.top - tooltipHeight - 10;
            if (x < 10) x = 10;
            if (x + tooltipWidth > window.innerWidth - 10) x = window.innerWidth - tooltipWidth - 10;
            if (y < window.scrollY + 10) {
                y = window.scrollY + bounds.bottom + 10;
            }
            this.tooltip.x = Math.round(x);
            this.tooltip.y = Math.round(y);
        },
        hideTooltip() {
            this.tooltip.show = false;
        },
        formatFullDate(dateInput) {
            if (!dateInput) return '';
            let d;
            if (typeof dateInput === 'string') {
                const datePart = dateInput.substring(0, 10);
                d = new Date(datePart);
            } else if (dateInput instanceof Date) {
                d = dateInput;
            } else {
                return '';
            }
            if (isNaN(d.getTime())) return '';
            const months = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'];
            return `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
        },
        getShortMonthName(mIdx) {
            return ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara'][mIdx] || '';
        },
        isEmergencyMed(medName) {
            let m = this.medications.find((x) => x.name.toLowerCase() === medName.toLowerCase());
            return m ? m.is_emergency : false;
        },
        getDailyEvents(dateStr) {
            let events = [];
            const currentAt = new Intl.DateTimeFormat('sv', { dateStyle: 'short', timeStyle: 'short' }).format(new Date());
            this.medicationLogs.forEach((l) => {
                if (l.at.startsWith(dateStr)) {
                    let isEmergency = this.isEmergencyMed(l.med);
                    events.push({ ...l, type: 'med', time: l.at.substring(11, 16), isEmergency });
                }
            });
            this.pressures.forEach((p) => {
                if (p.at.startsWith(dateStr)) events.push({ ...p, type: 'bp', time: p.at.substring(11, 16) });
            });
            this.weights.forEach((w) => {
                if (w.at.startsWith(dateStr)) events.push({ ...w, type: 'weight', time: w.at.substring(11, 16) });
            });
            this.tests.forEach((t) => {
                if (t.at.startsWith(dateStr)) events.push({ ...t, type: 'test', time: t.at.substring(11, 16) });
            });
            this.reports.forEach((r) => {
                if (r.at.startsWith(dateStr)) events.push({ ...r, type: 'report', time: r.at.substring(11, 16), at: r.at });
            });
            events.sort((a, b) => a.time.localeCompare(b.time));
            events.forEach((e) => {
                e.isPlan = e.at > currentAt;
            });
            return events;
        },
        async downloadRawMedicalData(mode = 'all') {
            try {
                const [u, h, m, mc, ml, p, w, t, ti, r] = await Promise.all([
                    fetch('data/users.json')
                        .then((r) => r.json())
                        .catch(() => []),
                    fetch('data/hospitals.json')
                        .then((r) => r.json())
                        .catch(() => []),
                    fetch('data/medications.json')
                        .then((r) => r.json())
                        .catch(() => []),
                    fetch('data/medication_changes.json')
                        .then((r) => r.json())
                        .catch(() => []),
                    fetch('data/medication_logs.json')
                        .then((r) => r.json())
                        .catch(() => []),
                    fetch('data/pressures.json')
                        .then((r) => r.json())
                        .catch(() => []),
                    fetch('data/weights.json')
                        .then((r) => r.json())
                        .catch(() => []),
                    fetch('data/tests.json')
                        .then((r) => r.json())
                        .catch(() => []),
                    fetch('data/test_items.json')
                        .then((r) => r.json())
                        .catch(() => []),
                    fetch('data/reports.json')
                        .then((r) => r.json())
                        .catch(() => []),
                ]);
                const patientData = u && u.length > 0 ? { name: u[0].name, email: u[0].email } : { name: 'Alaattin Sönmez', email: 'admin@medilog.test' };
                const clinicalContextSummary = {
                    patient_summary: 'Alaattin Sönmez (64 yaş, Erkek), 19 Şubat 2026 tarihinde, akut Tip A Aort Diseksiyonu ve Ciddi Aort Kapak Yetmezliği nedeniyle sırtına ve omurgasına yayılan, ani başlayan, yırtıcı karakterde şiddetli göğüs ve sırt ağrısı yaşamıştır.',
                    anatomical_surgical_modifications: [
                        'Dilate nativ asendan aort rezeke edildi (5.3 cm anevrizma); 32mm polyester Dacron vasküler greft ile replase edildi (değiştirildi).',
                        'Yetersiz nativ aort kapağı, 25mm Carbomedics çift yapraklı metalik mekanik protez kalp kapağı ile replase edildi.',
                        'Koroner arter butonları vasküler grefte implante edildi (Bentall Prosedürü 20 Şubat 2026 tarihinde tamamlandı).',
                        'Selektif antegrad serebral perfüzyon amacıyla sol brakiyal arter ve sağ common karotid artere (CCA) cerrahi kanülasyon uygulandı; ardından primer vasküler onarım sağlandı.',
                    ],
                    emergency_referral_pathway_feb_19_2026: [
                        { time: '17:21 - 17:22', hospital: 'Defne Devlet Hastanesi', clinical_actions: 'İlk acil başvuru. Kardiyak troponin bazal değeri ölçüldü. Hipertansif kriz tanısı konuldu. Acilen sevk edildi.' },
                        { time: '20:17 - 20:30', hospital: 'Mustafa Kemal Üniversitesi Araştırma Hastanesi', clinical_actions: 'Sistemik antikoagülasyon veya majör cerrahi öncesinde intrakraniyal kanama veya akut inmeyi ekarte etmek amacıyla acil kranyal değerlendirme (Diffüzyon MRG ve Kontrastsız Beyin BT) yapıldı.' },
                        { time: '21:42', hospital: 'Kırıkhan Devlet Hastanesi', clinical_actions: 'Kontrastlı Göğüs ve Batın BT Anjiyografisi tamamlandı. Aort kökünden iliak bifurkasyona kadar uzanan DeBakey Tip I / Stanford Tip A Aort Diseksiyonu ve asendan aort anevrizması doğrulandı.' },
                        { time: '23:30', hospital: 'Özel İskenderun Gelişim Hastanesi', clinical_actions: 'Doğrudan acil yatış sağlandı. Preoperatif hazırlıklar tamamlandı ve derin hipotermik sirkülatuar arrest altında acil açık kalp ameliyatı (Bentall Prosedürü) uygulandı.' },
                    ],
                };
                let filteredChanges = mc;
                let filteredLogs = ml;
                let filteredPressures = p;
                let filteredWeights = w;
                let filteredTests = t;
                let filteredTestItems = ti;
                let filteredReports = r;
                let clinicalInsightsData = {};
                if (mode === 'period') {
                    const start = this.startDate;
                    const end = this.endDate;
                    filteredChanges = mc.filter((c) => this.convertYmdHiToYmd(c.at) >= start && this.convertYmdHiToYmd(c.at) <= end);
                    filteredLogs = ml.filter((l) => l.at.substring(0, 10) >= start && l.at.substring(0, 10) <= end);
                    filteredPressures = p.filter((pr) => pr.at.substring(0, 10) >= start && pr.at.substring(0, 10) <= end);
                    filteredWeights = w.filter((wt) => wt.at.substring(0, 10) >= start && wt.at.substring(0, 10) <= end);
                    filteredTests = t.filter((test) => test.at.substring(0, 10) >= start && test.at.substring(0, 10) <= end);
                    const filteredTestIds = filteredTests.map((test) => test.id);
                    filteredTestItems = ti.filter((item) => filteredTestIds.includes(item.test_id));
                    filteredReports = r.filter((rep) => rep.at.substring(0, 10) >= start && rep.at.substring(0, 10) <= end);
                    clinicalInsightsData = {
                        selected_period: {
                            label: 'Seçili Dönem',
                            range: { start: this.startDate, end: this.endDate },
                            insights: [
                                {
                                    period: 'all',
                                    range: { start: this.startDate, end: this.endDate },
                                    html: this.generateDynamicInsight(this.startDate, this.endDate),
                                },
                            ],
                        },
                    };
                } else {
                    const presetToPeriod = {
                        3: 'last3',
                        7: 'last7',
                        10: 'last10',
                        15: 'last15',
                        30: 'last30',
                        45: 'last45',
                        60: 'last60',
                        90: 'last90',
                    };
                    const excludePreset = this.datePreset !== 'custom' && this.datePreset !== 'all' ? presetToPeriod[this.datePreset] || null : null;
                    const selectedPeriods = this.getInsightPeriods(this.endDate, this.startDate, excludePreset);
                    const allTimePeriods = this.getInsightPeriods(this.lastD, this.firstD, null);
                    clinicalInsightsData = {
                        selected_period: {
                            label: 'Seçili Dönem',
                            range: { start: this.startDate, end: this.endDate },
                            insights: selectedPeriods.map((p) => ({
                                period: p.label,
                                range: { start: p.start, end: p.end },
                                html: this.generateDynamicInsight(p.start, p.end),
                            })),
                        },
                        all_time: {
                            label: 'Tüm Zamanlar',
                            range: { start: this.firstD, end: this.lastD },
                            insights: allTimePeriods.map((p) => ({
                                period: p.label,
                                range: { start: p.start, end: p.end },
                                html: this.generateDynamicInsight(p.start, p.end),
                            })),
                        },
                    };
                }
                const masterOutput = {
                    export_date: new Date().toISOString(),
                    export_mode: mode === 'period' ? 'Selected Period Only' : 'All Historical Data',
                    date_range: mode === 'period' ? { start: this.startDate, end: this.endDate } : 'All-Time',
                    patient: patientData,
                    clinical_context: clinicalContextSummary,
                    clinical_evaluation_report: this.periodicClinicalReport,
                    clinical_insights: clinicalInsightsData,
                    hospitals: h,
                    medications: m,
                    medication_changes: filteredChanges,
                    medication_logs: filteredLogs,
                    blood_pressures: filteredPressures,
                    weights: filteredWeights,
                    tests: filteredTests,
                    lab_test_results: filteredTestItems,
                    reports: filteredReports,
                };
                const minifiedJson = JSON.stringify(masterOutput);
                const blob = new Blob([minifiedJson], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const slugifiedName = patientData.name
                    .toLowerCase()
                    .replace(/ğ/g, 'g')
                    .replace(/ü/g, 'u')
                    .replace(/ş/g, 's')
                    .replace(/ı/g, 'i')
                    .replace(/ö/g, 'o')
                    .replace(/ç/g, 'c')
                    .replace(/[^a-z0-9\s-]/g, '')
                    .trim()
                    .replace(/\s+/g, '-');
                const now = new Date();
                const timeStamp = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0') + '_' + String(now.getHours()).padStart(2, '0') + '-' + String(now.getMinutes()).padStart(2, '0') + '-' + String(now.getSeconds()).padStart(2, '0');
                const suffix = mode === 'period' ? `_period_${this.startDate}-to-${this.endDate}` : '_all-data';
                const link = document.createElement('a');
                link.href = url;
                link.download = `${timeStamp}_${slugifiedName}${suffix}.json`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(url);
            } catch (error) {
                console.error('Ham veriler indirilirken hata oluştu:', error);
                alert('Veriler indirilirken bir hata meydana geldi.');
            }
        },
    }));
}
