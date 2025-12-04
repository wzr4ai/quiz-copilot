<script>
import { initTheme } from './services/theme'

export default {
	onLaunch() {
		initTheme()
		console.log('App Launch')
	},
	onShow() {
		console.log('App Show')
	},
	onHide() {
		console.log('App Hide')
	}
}
</script>

<style>
	/*每个页面公共css */
</style>
