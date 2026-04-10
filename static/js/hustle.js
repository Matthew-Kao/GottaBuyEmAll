const $ = (sel, ctx = document) => ctx.querySelector(sel)
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)]

function handleSearch() {
  const q = $('#searchInput')?.value.trim()
  if (!q) return
  window.location.href = `/listings?q=${encodeURIComponent(q)}`
}

$('#searchInput')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') handleSearch()
})

function applyFilter(changedEl) {
  const params = new URLSearchParams(window.location.search)
  params.delete('page')

  const name  = changedEl.getAttribute('name')
  const value = changedEl.value

  if (value) {
    params.set(name, value)
  } else {
    params.delete(name)
  }

  window.location.search = params.toString()
}

$$('.flash').forEach(el => {
  setTimeout(() => {
    el.style.transition = 'opacity 0.4s'
    el.style.opacity = '0'
    setTimeout(() => el.remove(), 400)
  }, 4000)
})

if ('IntersectionObserver' in window) {
  const imgObs = new IntersectionObserver((entries, obs) => {
    entries.forEach(({ isIntersecting, target }) => {
      if (!isIntersecting) return
      target.style.opacity = '1'
      obs.unobserve(target)
    })
  }, { threshold: 0.1 })

  $$('img.card-img').forEach(img => {
    img.style.opacity = '0'
    img.style.transition = 'opacity 0.3s'
    imgObs.observe(img)
  })
}