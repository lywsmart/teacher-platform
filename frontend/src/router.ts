import {createRouter,createWebHistory} from 'vue-router'
import Login from './views/Login.vue'
import Dashboard from './views/Dashboard.vue'
import Achievements from './views/Achievements.vue'
import Annual from './views/Annual.vue'
import TitleApplications from './views/TitleApplications.vue'
import Files from './views/Files.vue'
import Analytics from './views/Analytics.vue'
import AISummaries from './views/AISummaries.vue'
import Profile from './views/Profile.vue'
import { api } from './api'
import Admin from './views/Admin.vue'
import Materials from './views/Materials.vue'
import Account from './views/Account.vue'
import Awards from './views/Awards.vue'
const router=createRouter({history:createWebHistory(),routes:[
 {path:'/login',component:Login,meta:{public:true}}, {path:'/',component:Dashboard},
 {path:'/achievements',component:Achievements},{path:'/annual',component:Annual},{path:'/titles',component:TitleApplications},
 {path:'/files',component:Files},{path:'/analytics',component:Analytics},{path:'/ai',component:AISummaries},
 {path:'/profile',component:Profile},{path:'/account',component:Account},
 {path:'/materials',component:Materials},
 {path:'/awards',component:Awards},
 {path:'/admin',component:Admin,meta:{admin:true}},
 {path:'/settings',redirect:'/admin'}
]})
router.beforeEach(async to => {
  const token = localStorage.getItem('token')
  if (!to.meta.public && !token) return '/login'
  if (to.path === '/login' && token) return '/'
  if (to.meta.admin) {
    try {
      if (!(await api.get('/auth/me')).data.is_admin) return '/'
    } catch {
      return '/'
    }
  }
})
export default router
