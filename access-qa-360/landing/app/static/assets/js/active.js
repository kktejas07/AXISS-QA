const currentPath = window.location.pathname.replace(/\/$/, '');

const subMenuItems = document.querySelectorAll('.sub-menu-item');
subMenuItems.forEach((item) => {
    const itemPath = new URL(item.href).pathname.replace(/\/$/, '');

    if (itemPath === currentPath) {
        item.classList.add('active');

        // Highlight all parent menus recursively
        let parentMenu = item.closest('.parent-menu-item');
        while (parentMenu && !parentMenu.classList.contains('processed')) {
            const parentLink = parentMenu.querySelector('a');
            if (parentLink) {
                parentLink.classList.add('active');
            }
            parentMenu.classList.add('processed');
            parentMenu = parentMenu.closest('.parent-parent-menu-item');
        }

        // Highlight the top-level parent menu
        const topLevelMenu = item.closest('.parent-parent-menu-item');
        if (topLevelMenu) {
            const topLevelLink = topLevelMenu.querySelector('.home-link');
            if (topLevelLink) {
                topLevelLink.classList.add('active');
            }
        }
    }
});