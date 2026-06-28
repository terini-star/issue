// Global Application State
const state = {
    currentLang: 'en',
    lastUpdated: null,
    trendsData: [],
    activeKeyword: null,
    countdownInterval: null,
    pollingInterval: null,
    width: 0,
    height: 0
};

// SVG and D3 Simulation Elements
let svg, mainGroup, simulation;
let isDragging = false; // Flag to check drag action vs click

// --- 1. PARTICLE CONSTELLATION BACKGROUND ---
function initParticleBackground() {
    const canvas = document.getElementById('particle-bg');
    const ctx = canvas.getContext('2d');
    
    let particles = [];
    const maxParticles = 60;
    const connectionDist = 110;
    let mouse = { x: null, y: null, active: false };

    function resizeCanvas() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    // Track mouse coordinates over dashboard
    window.addEventListener('mousemove', (e) => {
        mouse.x = e.clientX;
        mouse.y = e.clientY;
        mouse.active = true;
    });

    window.addEventListener('mouseleave', () => {
        mouse.active = false;
    });

    // Particle Object
    class Particle {
        constructor() {
            this.x = Math.random() * canvas.width;
            this.y = Math.random() * canvas.height;
            this.vx = (Math.random() - 0.5) * 0.4;
            this.vy = (Math.random() - 0.5) * 0.4;
            this.size = Math.random() * 1.5 + 1;
            this.alpha = Math.random() * 0.4 + 0.2;
            this.color = Math.random() > 0.5 ? '#00f2fe' : '#9d00ff';
        }

        update() {
            this.x += this.vx;
            this.y += this.vy;

            // Bounce on boundary
            if (this.x < 0 || this.x > canvas.width) this.vx *= -1;
            if (this.y < 0 || this.y > canvas.height) this.vy *= -1;
        }

        draw() {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
            ctx.fillStyle = this.color;
            ctx.globalAlpha = this.alpha;
            ctx.fill();
        }
    }

    // Populate particles
    for (let i = 0; i < maxParticles; i++) {
        particles.push(new Particle());
    }

    // Animation Loop
    function animate() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.globalAlpha = 1.0;
        
        // Draw connection lines
        for (let i = 0; i < particles.length; i++) {
            const p1 = particles[i];
            p1.update();
            p1.draw();

            // Check distance to other particles
            for (let j = i + 1; j < particles.length; j++) {
                const p2 = particles[j];
                const dx = p1.x - p2.x;
                const dy = p1.y - p2.y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < connectionDist) {
                    ctx.beginPath();
                    ctx.moveTo(p1.x, p1.y);
                    ctx.lineTo(p2.x, p2.y);
                    // Fade lines out based on distance
                    const alpha = (1 - dist / connectionDist) * 0.12;
                    ctx.strokeStyle = '#00f2fe';
                    ctx.globalAlpha = alpha;
                    ctx.lineWidth = 0.5;
                    ctx.stroke();
                }
            }

            // Connect to mouse
            if (mouse.active) {
                const dx = p1.x - mouse.x;
                const dy = p1.y - mouse.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < connectionDist * 1.3) {
                    ctx.beginPath();
                    ctx.moveTo(p1.x, p1.y);
                    ctx.lineTo(mouse.x, mouse.y);
                    const alpha = (1 - dist / (connectionDist * 1.3)) * 0.18;
                    ctx.strokeStyle = '#ff007f';
                    ctx.globalAlpha = alpha;
                    ctx.lineWidth = 0.7;
                    ctx.stroke();
                }
            }
        }

        requestAnimationFrame(animate);
    }
    animate();
}

// --- 2. D3.JS BUBBLE SIMULATION ---
function initBubbleChart() {
    svg = d3.select('#bubble-chart');
    mainGroup = svg.append('g').attr('class', 'main-group');
    
    // Zoom & Pan Handler
    const zoom = d3.zoom()
        .scaleExtent([0.5, 3])
        .on('zoom', (event) => {
            mainGroup.attr('transform', event.transform);
        });
        
    svg.call(zoom);

    updateDimensions();

    // Listen to resize
    window.addEventListener('resize', () => {
        updateDimensions();
        if (state.trendsData.length > 0) {
            renderBubbles(state.trendsData);
        }
    });
}

function updateDimensions() {
    const wrapper = document.getElementById('chart-wrapper');
    state.width = wrapper.clientWidth;
    state.height = wrapper.clientHeight;
    
    // Recenter simulation gravity forces
    if (simulation) {
        simulation
            .force('x', d3.forceX(state.width / 2).strength(0.08))
            .force('y', d3.forceY(state.height / 2).strength(0.08))
            .alpha(0.3)
            .restart();
    }
}

function renderBubbles(trends) {
    if (!trends || trends.length === 0) return;

    // Max counts for scale domain
    const maxCount = d3.max(trends, d => d.count) || 1;
    
    // Size Scale: Map mention count to radius size
    const radiusScale = d3.scaleSqrt()
        .domain([1, maxCount])
        .range([35, state.width < 600 ? 60 : 85]); // Slightly smaller on mobile

    // Prepare node coordinates/radii
    const nodes = trends.map(d => {
        // Carry over old coordinates if they exist to keep bubble transitions smooth
        const existingNode = simulation ? simulation.nodes().find(n => n.word === d.word) : null;
        return {
            ...d,
            radius: radiusScale(d.count),
            x: existingNode ? existingNode.x : state.width / 2 + (Math.random() - 0.5) * 100,
            y: existingNode ? existingNode.y : state.height / 2 + (Math.random() - 0.5) * 100
        };
    });

    // Setup / Restart Physics Forces
    if (!simulation) {
        simulation = d3.forceSimulation(nodes)
            .force('x', d3.forceX(state.width / 2).strength(0.08))
            .force('y', d3.forceY(state.height / 2).strength(0.08))
            .force('charge', d3.forceManyBody().strength(-12))
            .force('collide', d3.forceCollide(d => d.radius + 4).strength(0.85))
            .velocityDecay(0.25);
    } else {
        simulation.nodes(nodes);
        simulation.force('collide', d3.forceCollide(d => d.radius + 4).strength(0.85));
        simulation.alpha(0.6).restart();
    }

    // Bind Data to G elements
    const nodeSelection = mainGroup.selectAll('g.node')
        .data(nodes, d => d.word);

    // EXIT: fade out old items
    nodeSelection.exit()
        .transition()
        .duration(600)
        .style('opacity', 0)
        .remove();

    // ENTER: create new groupings
    const nodeEnter = nodeSelection.enter()
        .append('g')
        .attr('class', 'node')
        .style('opacity', 0)
        .call(drag(simulation));

    // Append base circles for new items
    nodeEnter.append('circle')
        .attr('class', d => `node-circle ${d.category.toLowerCase()}`)
        .attr('r', 0)
        .style('filter', d => `drop-shadow(0 0 6px var(--cat-${d.category.toLowerCase()}))`);

    // Append labels
    nodeEnter.append('text')
        .attr('class', 'node-label')
        .style('font-size', '1px'); // Scale up in transition

    // Append mentions count badge
    nodeEnter.append('text')
        .attr('class', 'node-count')
        .attr('dy', '15px')
        .style('opacity', 0);

    // MERGE ENTER + UPDATE
    const nodeMerge = nodeEnter.merge(nodeSelection);

    // Apply smooth visual transitions
    nodeMerge.transition()
        .duration(800)
        .style('opacity', 1);

    nodeMerge.select('circle')
        .transition()
        .duration(800)
        .attr('class', d => `node-circle ${d.category.toLowerCase()}`)
        .attr('r', d => d.radius);

    // Format truncated text labels to fit bubble size
    nodeMerge.select('text.node-label')
        .text(d => {
            const limit = Math.floor(d.radius / 5);
            return d.word.length > limit ? d.word.slice(0, limit - 1) + '..' : d.word;
        })
        .transition()
        .duration(800)
        .style('font-size', d => `${Math.max(10, Math.min(16, d.radius / 4.2))}px`)
        .attr('dy', d => d.count > 1 ? '-4px' : '0px');

    nodeMerge.select('text.node-count')
        .text(d => d.count > 1 ? `+${d.count}` : '')
        .attr('dy', d => `${d.radius * 0.35}px`)
        .transition()
        .duration(800)
        .style('opacity', d => d.count > 1 ? 0.7 : 0);

    // Interactions
    nodeMerge.on('mouseover', function(event, d) {
        if (isDragging) return;
        d3.select(this).select('circle')
            .transition()
            .duration(200)
            .attr('r', d.radius * 1.1)
            .style('filter', `drop-shadow(0 0 16px var(--cat-${d.category.toLowerCase()}))`);
    });

    nodeMerge.on('mouseout', function(event, d) {
        d3.select(this).select('circle')
            .transition()
            .duration(200)
            .attr('r', d.radius)
            .style('filter', `drop-shadow(0 0 6px var(--cat-${d.category.toLowerCase()}))`);
    });

    nodeMerge.on('click', function(event, d) {
        if (isDragging) return;
        event.stopPropagation();
        openDrawer(d);
        
        // Highlight active bubble
        mainGroup.selectAll('circle').classed('active-focus', false);
        d3.select(this).select('circle').classed('active-focus', true);
    });

    // Update positions on every physics tick
    simulation.on('tick', () => {
        nodeMerge.attr('transform', d => `translate(${d.x},${d.y})`);
    });
}

// Drag functionality for D3 nodes
function drag(simulation) {
    function dragstarted(event, d) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
        isDragging = false;
    }

    function dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
        isDragging = true;
    }

    function dragended(event, d) {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
        // Keep dragging flag true briefly to prevent firing click events right after drag release
        setTimeout(() => { isDragging = false; }, 50);
    }

    return d3.drag()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended);
}

// --- 3. TOOLTIP NEWS DRAWER INTERACTIVITY ---
function openDrawer(keywordData) {
    state.activeKeyword = keywordData.word;
    
    // Elements
    const drawer = document.getElementById('article-drawer');
    const title = document.getElementById('drawer-trend-title');
    const badge = document.getElementById('drawer-category-badge');
    const count = document.getElementById('drawer-mention-count');
    const list = document.getElementById('drawer-articles-list');
    
    // Set text contents
    title.innerText = keywordData.word;
    count.innerText = keywordData.articles.length;
    
    // Update Badge
    badge.innerText = keywordData.category;
    badge.className = `drawer-badge ${keywordData.category.toLowerCase()}`;
    
    // Clear lists
    list.innerHTML = '';
    
    // Populate cards
    keywordData.articles.forEach(article => {
        const card = document.createElement('div');
        card.className = 'article-card';
        
        // Format Date
        let dateStr = 'Recent';
        if (article.published) {
            try {
                const date = new Date(article.published);
                dateStr = date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
            } catch (e) {}
        }

        card.innerHTML = `
            <a href="${article.link}" target="_blank" class="article-title">${article.title}</a>
            <div class="article-footer">
                <span class="article-source">${article.source}</span>
                <span>${dateStr}</span>
                <a href="${article.link}" target="_blank" class="read-more-link">
                    Open RSS
                    <svg style="width:12px; height:12px; fill:currentColor" viewBox="0 0 24 24"><path d="M14 3h7v7h-2V6.41l-9 9L8.59 14l9-9H14V3zm-2 11H5V5h7V3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2v-7h-2v7h-7v-7z"/></svg>
                </a>
            </div>
        `;
        list.appendChild(card);
    });
    
    // Add active slide class
    drawer.classList.add('open');
}

function closeDrawer() {
    const drawer = document.getElementById('article-drawer');
    drawer.classList.remove('open');
    state.activeKeyword = null;
    mainGroup.selectAll('circle').classed('active-focus', false);
}

// --- 4. API FETCH & DATA SINK ---
async function fetchTrendsData(lang = 'en', force = false) {
    const loader = document.getElementById('loading-overlay');
    
    // Show loading overlay only on initial loads
    if (state.trendsData.length === 0 || force) {
        loader.classList.add('active');
    }

    try {
        const response = await fetch(`/api/trends?lang=${lang}`);
        if (!response.ok) throw new Error('API fetch failed');
        
        const data = await response.json();
        state.trendsData = data.trends;
        state.lastUpdated = data.last_updated;
        
        // Render D3 bubble nodes
        renderBubbles(state.trendsData);
        
        // Update Header Last Updated Time
        updateLastUpdatedDisplay(state.lastUpdated);
        
    } catch (e) {
        console.error("Error fetching trends from server API:", e);
    } finally {
        loader.classList.remove('active');
    }
}

// --- 5. TIMER AND POLLING LOGIC ---
function startCountdownTimer() {
    if (state.countdownInterval) clearInterval(state.countdownInterval);
    
    const countdownEl = document.getElementById('countdown-val');
    
    state.countdownInterval = setInterval(() => {
        if (!state.lastUpdated) return;
        
        const now = Date.now();
        // lastUpdated is in seconds, convert to ms
        const lastUpdatedMs = state.lastUpdated * 1000;
        const timePassed = now - lastUpdatedMs;
        const tenMinutesInMs = 10 * 60 * 1000;
        
        const timeRemaining = Math.max(0, tenMinutesInMs - (timePassed % tenMinutesInMs));
        
        const minutes = Math.floor(timeRemaining / 60000);
        const seconds = Math.floor((timeRemaining % 60000) / 1000);
        
        countdownEl.innerText = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }, 1000);
}

function updateLastUpdatedDisplay(timestamp) {
    const lastUpdatedEl = document.getElementById('last-updated-val');
    if (!timestamp) {
        lastUpdatedEl.innerText = '--:--:--';
        return;
    }
    
    const date = new Date(timestamp * 1000);
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    const seconds = date.getSeconds().toString().padStart(2, '0');
    
    lastUpdatedEl.innerText = `${hours}:${minutes}:${seconds}`;
}

function startRealTimePolling() {
    if (state.pollingInterval) clearInterval(state.pollingInterval);
    
    // Poll the status API every 30 seconds
    state.pollingInterval = setInterval(async () => {
        try {
            const res = await fetch('/api/status');
            if (!res.ok) return;
            const status = await res.json();
            
            // Check if the backend has updated since our last fetched time
            const lastUpdatedKey = state.currentLang === 'en' ? 'last_updated_en' : 'last_updated_ko';
            const backendLastUpdated = status[lastUpdatedKey];
            
            if (backendLastUpdated && backendLastUpdated > state.lastUpdated) {
                console.log("Backend update detected! Updating bubble chart in real-time...");
                fetchTrendsData(state.currentLang, false);
            }
        } catch (e) {
            console.error("Polling error:", e);
        }
    }, 30000);
}

// --- 6. EVENT LISTENERS & INITS ---
document.addEventListener('DOMContentLoaded', () => {
    // 1. Particle Background init
    initParticleBackground();
    
    // 2. Bubble Visualizer SVG init
    initBubbleChart();
    
    // 3. Close Drawer bindings
    document.getElementById('btn-close-drawer').addEventListener('click', closeDrawer);
    
    // Clicking outside bubbles and drawer closes it
    document.addEventListener('click', (e) => {
        const drawer = document.getElementById('article-drawer');
        const visualizer = document.querySelector('.visualizer-area');
        if (!drawer.contains(e.target) && visualizer.contains(e.target)) {
            closeDrawer();
        }
    });

    // 4. Toggle Language Button bindings
    const btnEn = document.getElementById('btn-en');
    const btnKo = document.getElementById('btn-ko');
    
    function switchLanguage(lang) {
        if (state.currentLang === lang) return;
        state.currentLang = lang;
        closeDrawer();
        
        if (lang === 'en') {
            btnEn.classList.add('active');
            btnKo.classList.remove('active');
        } else {
            btnKo.classList.add('active');
            btnEn.classList.remove('active');
        }
        
        fetchTrendsData(lang, true);
    }
    
    btnEn.addEventListener('click', () => switchLanguage('en'));
    btnKo.addEventListener('click', () => switchLanguage('ko'));
    
    // 5. Initial Data Fetch
    fetchTrendsData('en', true);
    
    // 6. Start Sync Timers
    startCountdownTimer();
    startRealTimePolling();
});
