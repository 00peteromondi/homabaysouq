// Main initialization file
import { imageUtils } from './utils/image-utils.js';
import { favoriteUtils } from './utils/favorite-utils.js';
import { galleryUtils } from './utils/gallery-utils.js';

// Initialize all utilities when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Setup image handling
    imageUtils.setupLazyLoading(document);
    
    // Setup favorite functionality
    favoriteUtils.setupFavoriteButtons(document);
    
    // Setup gallery if on detail page
    if (document.querySelector('.listing-gallery-container')) {
        galleryUtils.setupGallery(document);
    }
});